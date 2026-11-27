"""VoiceStudio native CLI & HTTP TTS client for avatar-journal.

Primary interface: official VoiceStudio CLI (`voicestudio.exe speak --json`)
installed alongside the local VoiceStudio app, with HTTP `/v1/audio/speech`
fallback on port 3900 and optional offline Piper fallback.

Emotion & `--instruct` semantics (verified in VoiceStudio v0.5.8 backend):
  - `omnivoice` (default): `instruct_vocabulary = "tags"`,
    `instruct_directs_delivery = False`. Freeform prose in `--instruct` is
    discarded by `sanitize_instruct()`; only whitelist voice-design tags
    (`male`/`female`, age, pitch, `whisper`, accent) survive. Emotion comes
    from punctuation, semantics, cloned reference audio, and inline tags.
  - `voxcpm2` (48 kHz studio): `instruct_vocabulary = "freeform"`,
    `instruct_directs_delivery = True`, supports Portuguese (`pt`). Ideal when
    using natural-language emotion/acting directions in `--instruct`.
  - `cosyvoice` / `indextts2`: support emotion controls, but do not declare
    Portuguese (`pt`).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path
from typing import Any, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

DEFAULT_VOICESTUDIO_URL = os.getenv("VOICESTUDIO_BASE_URL", "http://127.0.0.1:3900")
DEFAULT_VOICE = os.getenv("VOICESTUDIO_VOICE") or os.getenv("VOICECRAFT_VOICE") or "Ale-empolgado"
DEFAULT_ENGINE = os.getenv("VOICESTUDIO_ENGINE", "omnivoice")
DEFAULT_VOICESTUDIO_CLI = os.getenv(
    "VOICESTUDIO_CLI",
    r"C:\Users\Pires\AppData\Local\Programs\VoiceStudio\resources\cli\voicestudio.exe",
)

DECISION_CATEGORY = "voice_selection"
DECISION_SUBJECT = "Narration TTS provider"

# Exact whitelist enforced by VoiceStudio's `omnivoice/utils/voice_design.py`.
OMNIVOICE_TAGS_WHITELIST: frozenset[str] = frozenset({
    "male", "female",
    "child", "teenager", "young adult", "middle-aged", "elderly",
    "very low pitch", "low pitch", "moderate pitch", "high pitch", "very high pitch",
    "whisper",
    "american accent", "british accent", "australian accent", "chinese accent",
    "canadian accent", "indian accent", "korean accent", "portuguese accent",
    "russian accent", "japanese accent",
})

ENGINE_SPECS: dict[str, dict[str, Any]] = {
    "omnivoice": {
        "vocab": "tags",
        "instruct_directs_delivery": False,
        "supports_emotion": False,
        "supports_pt": True,
    },
    "omnivoice_gguf": {
        "vocab": "tags",
        "instruct_directs_delivery": False,
        "supports_emotion": False,
        "supports_pt": True,
    },
    "voxcpm2": {
        "vocab": "freeform",
        "instruct_directs_delivery": True,
        "supports_emotion": False,
        "supports_pt": True,
    },
    "cosyvoice": {
        "vocab": "freeform",
        "instruct_directs_delivery": True,
        "supports_emotion": False,
        "supports_pt": False,
    },
    "indextts2": {
        "vocab": "freeform",
        "instruct_directs_delivery": False,
        "supports_emotion": True,
        "supports_pt": False,
    },
}

ENGINE_TAGS: dict[str, set[str]] = {
    "omnivoice": {
        "pause", "slow", "fast", "emphasis", "spell", "laughter", "sigh",
        "confirmation-en", "question-en", "question-ah", "question-oh",
        "question-ei", "question-yi", "surprise-ah", "surprise-oh",
        "surprise-wa", "surprise-yo", "dissatisfaction-hnn",
    },
    "voicestudio": {
        "pause", "slow", "fast", "emphasis", "spell", "laughter", "sigh",
        "confirmation-en", "question-en", "question-ah", "question-oh",
        "question-ei", "question-yi", "surprise-ah", "surprise-oh",
        "surprise-wa", "surprise-yo", "dissatisfaction-hnn",
    },
    "cosyvoice": {"pause", "slow", "fast", "emphasis", "spell", "laughter", "sigh", "breath"},
    "indextts2": {"pause", "slow", "fast", "emphasis", "spell", "emotion"},
    "voxcpm2": {"pause", "slow", "fast", "emphasis", "spell", "emotion"},
    "piper": {"pause"},
}


def find_voicestudio_cli(override: Optional[str] = None) -> Optional[str]:
    """Locate the native `voicestudio.exe` CLI binary."""
    candidates = [
        override,
        os.getenv("VOICESTUDIO_CLI"),
        shutil.which("voicestudio"),
        DEFAULT_VOICESTUDIO_CLI,
    ]
    for cand in candidates:
        if cand and Path(cand).is_file():
            return str(Path(cand))
    return None


def _normalize_engine(engine: Optional[str]) -> str:
    raw = (engine or DEFAULT_ENGINE).strip().lower()
    if raw in ("", "voicestudio", "tts-1", "tts-1-hd", "gpt-4o-mini-tts", "auto"):
        return "omnivoice"
    return raw


def _normalize_language(lang: Optional[str]) -> str:
    raw = (lang or "pt").strip()
    if raw.lower().startswith("pt"):
        return "pt"
    return raw


def validate_instruct(
    instruct: Optional[str],
    engine: Optional[str] = None,
    language: Optional[str] = "pt",
) -> dict[str, Any]:
    """Validate `--instruct` against the selected VoiceStudio engine capabilities."""
    eng = _normalize_engine(engine)
    lang = _normalize_language(language)
    spec = ENGINE_SPECS.get(
        eng,
        {"vocab": "freeform", "instruct_directs_delivery": False, "supports_emotion": False, "supports_pt": True},
    )
    warnings: list[str] = []
    dropped_tokens: list[str] = []
    clean_in = (instruct or "").strip()
    sanitized = clean_in

    if lang == "pt" and not spec["supports_pt"]:
        warnings.append(
            f"Engine '{eng}' nao declara suporte a portugues ('pt'); prefira 'omnivoice' ou 'voxcpm2'."
        )

    if clean_in and spec["vocab"] == "tags":
        kept: list[str] = []
        for part in re.split(r"[,，]", clean_in):
            tok = part.strip().lower()
            if not tok:
                continue
            if tok in OMNIVOICE_TAGS_WHITELIST:
                kept.append(tok)
            else:
                dropped_tokens.append(part.strip())
        sanitized = ", ".join(kept)
        if dropped_tokens:
            warnings.append(
                f"Engine '{eng}' usa vocabulario 'tags' e descarta prosa livre ({dropped_tokens}); "
                "para direcao emocional natural em PT-BR use '--engine voxcpm2', ou guie o OmniVoice por pontuacao e semantica."
            )

    return {
        "engine": eng,
        "language": lang,
        "vocab": spec["vocab"],
        "instruct_directs_delivery": spec["instruct_directs_delivery"],
        "supports_emotion": spec["supports_emotion"],
        "supports_pt": spec["supports_pt"],
        "raw_instruct": clean_in or None,
        "sanitized_instruct": sanitized or None,
        "dropped_tokens": dropped_tokens,
        "valid": len(warnings) == 0,
        "warnings": warnings,
    }


def analyze_expression(text: str, engine: str = "omnivoice") -> dict[str, Any]:
    """List inline bracket tags in `text` and flag tags ignored by `engine`."""
    eng = _normalize_engine(engine) if engine not in ENGINE_TAGS else engine
    found = re.findall(r"\[([^\[\]]{1,60})\]", text)
    tags: list[str] = []
    for raw in found:
        name = raw.strip().lower()
        if name.startswith("/"):
            name = name[1:]
        name = re.split(r"[\s:]", name, maxsplit=1)[0]
        if name and name not in tags:
            tags.append(name)
    supported = ENGINE_TAGS.get(eng, ENGINE_TAGS["omnivoice"])
    unsupported = [t for t in tags if t not in supported]
    warnings: list[str] = []
    for tag in unsupported:
        if tag == "breath":
            warnings.append("[breath] e renderizado apenas no CosyVoice 3; OmniVoice pode ler literalmente.")
        elif tag == "emotion":
            warnings.append("[emotion:...] e da camada de historias/audiobook; passe emocao via '--instruct' com engine adequado.")
        else:
            warnings.append(f"[{tag}] nao e suportado por '{eng}' e pode ser falado literalmente.")
    return {"engine": eng, "tags": tags, "unsupported": unsupported, "warnings": warnings}


def _port_open(base_url: str, timeout: float = 1.5) -> bool:
    try:
        parsed = urllib.parse.urlsplit(base_url)
        with socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or 3900), timeout=timeout):
            return True
    except OSError:
        return False


def flush_memory(base_url: str = DEFAULT_VOICESTUDIO_URL, timeout: float = 5.0) -> dict[str, Any]:
    """Unload active TTS weights from VRAM via VoiceStudio's flush endpoint."""
    url = base_url.rstrip("/") + "/system/flush-memory?unload_model=true"
    try:
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return {"ok": True, "response": json.loads(raw)}
            except Exception:
                return {"ok": True, "response": raw}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def run_cli_command(
    args: list[str],
    *,
    cli_path: Optional[str] = None,
    base_url: str = DEFAULT_VOICESTUDIO_URL,
    timeout: float = 120.0,
) -> tuple[int, Any, str]:
    """Run an official `voicestudio.exe` command with `--json` output."""
    exe = find_voicestudio_cli(cli_path)
    if not exe:
        return 127, None, "voicestudio.exe CLI nao encontrado"
    cmd = [exe, "--url", base_url.rstrip("/"), "--json", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    parsed: Any = out
    if out:
        try:
            parsed = json.loads(out)
        except Exception:
            parsed = out
    return proc.returncode, parsed, err


def health_check(base_url: str = DEFAULT_VOICESTUDIO_URL, cli_path: Optional[str] = None) -> dict[str, Any]:
    """Check whether VoiceStudio CLI and local HTTP server (:3900) are ready."""
    exe = find_voicestudio_cli(cli_path)
    online = _port_open(base_url)
    cli_status = None
    if exe:
        rc, parsed, err = run_cli_command(["status"], cli_path=exe, base_url=base_url, timeout=15.0)
        cli_status = parsed if isinstance(parsed, dict) else {"rc": rc, "raw": parsed, "stderr": err}
    return {
        "online": online or bool(isinstance(cli_status, dict) and cli_status.get("running")),
        "base_url": base_url,
        "cli_path": exe,
        "cli_status": cli_status,
    }


def _post_voicestudio_http(
    body: dict[str, Any],
    base_url: str,
    timeout: float = 1800.0,
) -> tuple[bytes, dict[str, str]]:
    req = urllib.request.Request(
        base_url.rstrip("/") + "/v1/audio/speech",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        headers = {k.lower(): v for k, v in resp.headers.items()}
    if not raw:
        raise RuntimeError("VoiceStudio retornou payload de audio vazio")
    return raw, headers


def _find_ffprobe(override: Optional[str] = None) -> Optional[str]:
    if override and Path(override).is_file():
        return override
    for candidate in (r"D:\Utilitarios\ffmpeg\bin\ffprobe.exe", r"C:\ffmpeg\bin\ffprobe.exe"):
        if Path(candidate).is_file():
            return candidate
    return shutil.which("ffprobe")


def probe_duration(audio_path: Path, ffprobe_override: Optional[str] = None) -> Optional[float]:
    ffprobe = _find_ffprobe(ffprobe_override)
    if ffprobe:
        try:
            out = subprocess.run(
                [
                    ffprobe, "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path),
                ],
                capture_output=True, text=True, timeout=30,
            )
            if out.returncode == 0 and out.stdout.strip():
                return round(float(out.stdout.strip()), 3)
        except Exception:
            pass
    try:
        with wave.open(str(audio_path), "rb") as wf:
            return round(wf.getnframes() / float(wf.getframerate()), 3)
    except Exception:
        return None


def append_decision(
    decision_log_path: Path,
    selected: str,
    reason: str,
    options: list[dict[str, Any]],
    stage: str = "assets",
    user_approved: bool = True,
    confidence: float = 0.95,
) -> Optional[str]:
    path = Path(decision_log_path)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    decisions = payload.setdefault("decisions", [])
    existing_ids = {str(d.get("decision_id")) for d in decisions}
    idx = len(decisions) + 1
    new_id = f"d-{idx:03d}"
    while new_id in existing_ids:
        idx += 1
        new_id = f"d-{idx:03d}"
    decisions.append({
        "decision_id": new_id,
        "stage": stage,
        "category": DECISION_CATEGORY,
        "subject": DECISION_SUBJECT,
        "options_considered": options,
        "selected": selected,
        "reason": reason,
        "user_visible": True,
        "user_approved": user_approved,
        "confidence": confidence,
    })
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return new_id


class VoiceStudioTTS(BaseTool):
    name = "voicestudio_tts"
    version = "2.0.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "voicestudio"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["app:voicestudio@127.0.0.1:3900"]
    install_instructions = (
        "Inicie o VoiceStudio desktop/backend na porta 3900 e confirme com:\n"
        f"  \"{DEFAULT_VOICESTUDIO_CLI}\" status --json"
    )
    agent_skills = ["text-to-speech"]
    capabilities = ["text_to_speech", "voice_cloning", "native_cli", "emotion_instruct", "piper_fallback"]
    supports = {
        "voice_cloning": True,
        "multilingual": True,
        "offline": True,
        "native_audio": True,
        "ssml": False,
        "emotion": True,
        "style_prompt": True,
    }
    best_for = [
        "PT-BR cloned voice narration via official voicestudio.exe CLI",
        "expressive emotional delivery using --engine voxcpm2 --instruct",
        "consistent local zero-cost narration with optional Piper fallback",
    ]
    not_good_for = ["freeform emotion prose sent to tag-only OmniVoice engine"]
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=20)
    retry_policy = RetryPolicy(max_retries=1, backoff_seconds=1.0)
    idempotency_key_fields = ["text", "voice", "engine", "instruct", "language", "speed", "seed"]

    input_schema = {
        "type": "object",
        "required": ["text", "output_path"],
        "properties": {
            "text": {"type": "string"},
            "output_path": {"type": "string"},
            "voice": {"type": ["string", "null"], "default": DEFAULT_VOICE},
            "engine": {"type": ["string", "null"], "default": DEFAULT_ENGINE},
            "instruct": {"type": ["string", "null"], "default": None},
            "instructions": {"type": ["string", "null"], "default": None},
            "style": {"type": ["string", "null"], "default": None},
            "language": {"type": "string", "default": "pt"},
            "speed": {"type": "number", "default": 1.0},
            "seed": {"type": ["integer", "null"], "default": None},
            "format": {"type": "string", "enum": ["wav", "mp3"], "default": "wav"},
            "voicestudio_url": {"type": "string", "default": DEFAULT_VOICESTUDIO_URL},
            "voicestudio_cli": {"type": ["string", "null"], "default": None},
            "request_timeout": {"type": "number", "default": 600.0},
            "fallback_to_piper": {"type": "boolean", "default": True},
            "piper_model": {"type": "string", "default": "pt_BR-faber-medium"},
            "piper_length_scale": {"type": "number", "default": 0.85},
            "decision_log": {"type": ["string", "null"], "default": None},
            "decision_reason": {"type": ["string", "null"], "default": None},
            "stage": {"type": "string", "default": "assets"},
            "ffprobe": {"type": ["string", "null"], "default": None},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "audio_path": {"type": "string"},
            "provider_used": {"type": "string"},
            "transport_used": {"type": "string"},
            "voice_used": {"type": ["string", "null"]},
            "engine_used": {"type": ["string", "null"]},
            "duration_seconds": {"type": ["number", "null"]},
            "fallback_used": {"type": "boolean"},
            "fallback_reason": {"type": ["string", "null"]},
            "instruct_validation": {"type": "object"},
            "expression": {"type": "object"},
            "decision_id": {"type": ["string", "null"]},
            "elapsed_seconds": {"type": "number"},
        },
    }

    def get_status(self) -> ToolStatus:
        if find_voicestudio_cli() or _port_open(DEFAULT_VOICESTUDIO_URL, timeout=1.0):
            return ToolStatus.AVAILABLE
        return ToolStatus.DEGRADED

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        text = str(inputs.get("text") or "").strip()
        if not text:
            return ToolResult(success=False, error="text is required")

        out_path = Path(str(inputs.get("output_path") or "")).expanduser()
        if not out_path.is_absolute():
            out_path = Path.cwd() / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)

        voice = str(inputs.get("voice") or DEFAULT_VOICE).strip()
        engine = _normalize_engine(inputs.get("engine") or inputs.get("model"))
        lang = _normalize_language(inputs.get("language"))
        speed = float(inputs.get("speed") or 1.0)
        seed = inputs.get("seed")
        fmt = str(inputs.get("format") or "wav").lower()
        vs_url = str(inputs.get("voicestudio_url") or DEFAULT_VOICESTUDIO_URL)
        cli_exe = find_voicestudio_cli(inputs.get("voicestudio_cli"))
        timeout = float(inputs.get("request_timeout", 600.0))
        fallback_enabled = bool(inputs.get("fallback_to_piper", True))

        raw_instruct = inputs.get("instruct") or inputs.get("instructions") or inputs.get("style")
        instruct_val = validate_instruct(raw_instruct, engine=engine, language=lang)
        for w in instruct_val["warnings"]:
            print(f"[voicestudio_tts] instruct: {w}", file=sys.stderr)

        effective_instruct = instruct_val["sanitized_instruct"] if engine in ("omnivoice", "omnivoice_gguf") else (
            str(raw_instruct).strip() if raw_instruct else None
        )
        expression = analyze_expression(text, engine)
        for w in expression["warnings"]:
            print(f"[voicestudio_tts] expressividade: {w}", file=sys.stderr)

        transport_used = ""
        fallback_used = False
        fallback_reason: Optional[str] = None
        provider_used = "voicestudio"

        # 1) Primary: official `voicestudio.exe speak` CLI
        if cli_exe:
            tmp_dir = Path(tempfile.mkdtemp(prefix="voicestudio_speak_"))
            txt_file = tmp_dir / "input_utf8.txt"
            txt_file.write_text(text, encoding="utf-8")
            try:
                cmd = [
                    cli_exe, "--url", vs_url.rstrip("/"), "--json",
                    "speak", "--voice", voice, "--engine", engine, "--language", lang,
                    "--output", str(out_path), "--overwrite", "--text-file", str(txt_file),
                ]
                if abs(speed - 1.0) > 1e-4:
                    cmd.extend(["--speed", f"{speed:.3f}"])
                if seed is not None:
                    cmd.extend(["--seed", str(int(seed))])
                if effective_instruct:
                    cmd.extend(["--instruct", effective_instruct])

                proc = subprocess.run(
                    cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
                )
                if proc.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0:
                    transport_used = "voicestudio-cli"
                else:
                    msg = (proc.stderr or proc.stdout or f"exit {proc.returncode}").strip()
                    fallback_reason = f"voicestudio CLI failed: {msg[:350]}"
            except Exception as exc:
                fallback_reason = f"voicestudio CLI exception: {exc}"
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
        else:
            fallback_reason = "voicestudio.exe CLI nao encontrado"

        # 2) HTTP Fallback: direct /v1/audio/speech on :3900 if open
        if not transport_used and _port_open(vs_url, timeout=1.5):
            body: dict[str, Any] = {
                "model": engine,
                "voice": voice,
                "input": text,
                "response_format": fmt,
                "language": lang,
                "speed": speed,
            }
            if effective_instruct:
                body["instruct"] = effective_instruct
            if seed is not None:
                body["seed"] = int(seed)
            for k in ("paragraph_gap_ms", "position_temperature", "class_temperature", "num_step", "postprocess_output"):
                if inputs.get(k) not in (None, ""):
                    body[k] = inputs[k]
            try:
                audio_bytes, _ = _post_voicestudio_http(body, vs_url, timeout=timeout)
                tmp = out_path.with_suffix(out_path.suffix + ".part")
                tmp.write_bytes(audio_bytes)
                tmp.replace(out_path)
                transport_used = "voicestudio-http"
                fallback_reason = None
            except Exception as exc:
                fallback_reason = f"{fallback_reason} | HTTP fallback: {exc}" if fallback_reason else str(exc)

        # 3) Optional offline Piper fallback
        if not transport_used:
            if not fallback_enabled:
                return ToolResult(
                    success=False,
                    error=f"VoiceStudio falhou e fallback desativado: {fallback_reason}",
                    data={"instruct_validation": instruct_val, "expression": expression},
                )
            fallback_used = True
            fb = self._run_piper_fallback(inputs, text, out_path)
            if not fb.success:
                return ToolResult(
                    success=False,
                    error=f"VoiceStudio falhou ({fallback_reason}) e Piper fallback falhou ({fb.error})",
                )
            provider_used = "piper"
            transport_used = "piper-offline"
            voice = str(inputs.get("piper_model") or "pt_BR-faber-medium")
            engine = "piper"

        duration = probe_duration(out_path, inputs.get("ffprobe"))
        decision_id = None
        if inputs.get("decision_log"):
            decision_id = append_decision(
                Path(str(inputs["decision_log"])),
                selected=f"{provider_used}:{engine}",
                reason=str(inputs.get("decision_reason") or f"VoiceStudio ({transport_used}) voice={voice} engine={engine}"),
                options=[{"option_id": transport_used, "voice": voice, "engine": engine}],
                stage=str(inputs.get("stage") or "assets"),
            )

        return ToolResult(
            success=True,
            data={
                "audio_path": str(out_path),
                "provider_used": provider_used,
                "transport_used": transport_used,
                "voice_used": voice,
                "engine_used": engine,
                "duration_seconds": duration,
                "fallback_used": fallback_used,
                "fallback_reason": fallback_reason,
                "instruct_validation": instruct_val,
                "expression": expression,
                "decision_id": decision_id,
                "elapsed_seconds": round(time.time() - started, 2),
            },
        )

    def _run_piper_fallback(self, inputs: dict[str, Any], text: str, out_path: Path) -> ToolResult:
        try:
            from tools.audio.piper_tts import PiperTTS

            return PiperTTS().execute({
                "text": text,
                "output_path": str(out_path),
                "model": inputs.get("piper_model") or "pt_BR-faber-medium",
                "length_scale": float(inputs.get("piper_length_scale") or 0.85),
            })
        except Exception as exc:
            return ToolResult(success=False, error=f"{type(exc).__name__}: {exc}")


def _cli() -> int:
    p = argparse.ArgumentParser(description="VoiceStudio native CLI/HTTP TTS client")
    p.add_argument("--text", help="Text to synthesize")
    p.add_argument("--text-file", help="UTF-8 text file to synthesize")
    p.add_argument("--out", help="Output audio path (.wav/.mp3)")
    p.add_argument("--voice", default=DEFAULT_VOICE, help=f"Saved VoiceStudio voice (default: {DEFAULT_VOICE})")
    p.add_argument("--engine", default=DEFAULT_ENGINE, help="TTS engine: omnivoice, voxcpm2, cosyvoice, indextts2")
    p.add_argument("--instruct", default=None, help="Voice/emotion direction (--instruct)")
    p.add_argument("--instructions", default=None, help="Alias for --instruct")
    p.add_argument("--style", default=None, help="Legacy style alias (e.g., whisper)")
    p.add_argument("--language", default="pt", help="ISO language code (default: pt)")
    p.add_argument("--speed", type=float, default=1.0, help="Speech speed multiplier (0.25-4.0)")
    p.add_argument("--seed", type=int, default=None, help="Reproducible generation seed")
    p.add_argument("--format", default="wav", choices=["wav", "mp3"])
    p.add_argument("--voicestudio-url", default=DEFAULT_VOICESTUDIO_URL)
    p.add_argument("--no-piper-fallback", action="store_true", help="Fail instead of falling back to Piper")
    p.add_argument("--status", action="store_true", help="Show VoiceStudio status JSON")
    p.add_argument("--engines", action="store_true", help="List available VoiceStudio engines JSON")
    p.add_argument("--voices", action="store_true", help="List saved VoiceStudio voices JSON")
    p.add_argument("--flush-memory", action="store_true", help="Unload GPU TTS weights via :3900")
    p.add_argument("--lint-tags", action="store_true", help="Lint bracket tags and --instruct compatibility")
    p.add_argument("--decision-log", default=None)
    # Legacy no-op compat flags
    p.add_argument("--provider", default="voicestudio", help=argparse.SUPPRESS)
    p.add_argument("--profile", default="narrador", help=argparse.SUPPRESS)
    p.add_argument("--model", default=None, help=argparse.SUPPRESS)
    p.add_argument("--paragraph-gap-ms", type=int, default=None, help=argparse.SUPPRESS)
    p.add_argument("--keep-silences", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args()

    if args.status:
        print(json.dumps(health_check(args.voicestudio_url), indent=2, ensure_ascii=False))
        return 0
    if args.flush_memory:
        print(json.dumps(flush_memory(args.voicestudio_url), indent=2, ensure_ascii=False))
        return 0
    if args.engines:
        rc, parsed, err = run_cli_command(["engines", "list"], base_url=args.voicestudio_url)
        print(json.dumps(parsed if parsed is not None else {"rc": rc, "error": err}, indent=2, ensure_ascii=False))
        return 0 if rc == 0 else 1
    if args.voices:
        rc, parsed, err = run_cli_command(["voices", "list"], base_url=args.voicestudio_url)
        print(json.dumps(parsed if parsed is not None else {"rc": rc, "error": err}, indent=2, ensure_ascii=False))
        return 0 if rc == 0 else 1

    text = args.text
    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8")

    eff_engine = args.model or args.engine
    eff_instruct = args.instruct or args.instructions or args.style

    if args.lint_tags:
        print(json.dumps({
            "expression": analyze_expression(text or "", eff_engine),
            "instruct_validation": validate_instruct(eff_instruct, engine=eff_engine, language=args.language),
        }, indent=2, ensure_ascii=False))
        return 0

    if not args.out or not text:
        p.error("--out and (--text or --text-file) are required")

    res = VoiceStudioTTS().execute({
        "text": text,
        "output_path": args.out,
        "voice": args.voice,
        "engine": eff_engine,
        "instruct": eff_instruct,
        "language": args.language,
        "speed": args.speed,
        "seed": args.seed,
        "format": args.format,
        "voicestudio_url": args.voicestudio_url,
        "fallback_to_piper": not args.no_piper_fallback,
        "decision_log": args.decision_log,
    })
    print(json.dumps(dataclasses.asdict(res), indent=2, ensure_ascii=False, default=str))
    return 0 if res.success else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
