"""VoiceCraft local TTS bridge (http://127.0.0.1:8090).

VoiceCraft is a local HTTP studio that fronts several speech backends. This
tool talks to its documented JSON API, keeps the principal configured voice
consistent across scenes, and falls back to the local Piper model whenever the
service is offline or refuses a request.

API contract (see D:\\Utilitarios\\VoiceCraft\\tts_service.py):
  GET  /health                -> {"status": "ok", "providers": [...]}
  GET  /api/voices            -> voices for a provider/language
  POST /api/tts               -> audio bytes (JSON body, see input_schema)
      body keys: text, language, provider, voice, model, instructions,
                 format, profile, rate, pitch
      response headers: X-TTS-Provider, X-TTS-Voice, X-TTS-Profile,
                        X-TTS-Emotion, X-TTS-Elapsed

Cost note: the local service rotates free-tier providers (Gemini/AI Studio in
the default `auto` chain). It is not a paid API and it is not a voice-cloning
model; "voice cloning" is explicitly out of scope in VoiceCraft's spec, so the
tool exposes the principal configured voice instead.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path
from typing import Any, Optional

# Allow `python tools/voice_craft_tts.py` (script mode) imports.
if __package__ in (None, ""):
    import sys

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

DEFAULT_BASE_URL = os.getenv("VOICECRAFT_BASE_URL", "http://127.0.0.1:8090")
DEFAULT_VOICESTUDIO_URL = os.getenv("VOICESTUDIO_BASE_URL", "http://127.0.0.1:3900")
DEFAULT_VOICE = os.getenv("VOICECRAFT_VOICE", "Ale-empolgado")
DEFAULT_PROFILE = "narrador"
DEFAULT_MODEL = "gemini-2.5-flash-preview-tts"
DEFAULT_INSTRUCTIONS = (
    "Fale em ritmo rápido e firme de telejornal, com dicção clara e sem pausas longas."
)

DECISION_CATEGORY = "voice_selection"
DECISION_SUBJECT = "Narration TTS provider"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _http_json(url: str, timeout: float) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _port_open(base_url: str, timeout: float = 1.5) -> bool:
    try:
        parsed = urllib.parse.urlsplit(base_url)
        with socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or 80), timeout=timeout):
            return True
    except OSError:
        return False


def health_check(base_url: str = DEFAULT_BASE_URL, timeout: float = 12.0) -> dict[str, Any]:
    """Return {"online": bool, "detail": str, "providers": [...]}."""
    url = base_url.rstrip("/") + "/health"
    try:
        payload = _http_json(url, timeout)
        status = str(payload.get("status") or "").lower()
        online = status in ("ok", "healthy", "up")
        return {
            "online": online,
            "detail": f"status={status or 'unknown'}",
            "providers": payload.get("providers", []),
            "base_url": base_url,
        }
    except Exception as exc:  # offline, DNS, timeout, invalid JSON
        return {
            "online": False,
            "detail": f"{type(exc).__name__}: {exc}",
            "providers": [],
            "base_url": base_url,
        }


def list_voices(
    provider: str = "gemini",
    language: str = "pt-BR",
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"provider": provider, "language": language})
    payload = _http_json(f"{base_url.rstrip('/')}/api/voices?{query}", timeout)
    return payload.get("voices", [])


def _post_tts(
    body: dict[str, Any],
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 180.0,
) -> tuple[bytes, dict[str, str]]:
    req = urllib.request.Request(
        base_url.rstrip("/") + "/api/tts",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        headers = {k.lower(): v for k, v in resp.headers.items()}
    if not raw:
        raise RuntimeError("VoiceCraft returned an empty audio payload")
    return raw, headers


def _post_voicestudio(
    body: dict[str, Any],
    base_url: str,
    timeout: float = 1800.0,
) -> tuple[bytes, dict[str, str]]:
    """Direct VoiceStudio OpenAI-compatible call (the cloned-voice home).

    VoiceCraft proxies VoiceStudio with a 90s cap that is far too short for a
    clone running on CPU, so cloned voices are called here directly.
    """
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
        raise RuntimeError("VoiceStudio returned an empty audio payload")
    return raw, headers


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------


def _find_ffprobe(override: Optional[str] = None) -> Optional[str]:
    if override:
        return override
    env = os.getenv("FFPROBE_PATH")
    if env and Path(env).is_file():
        return env
    for candidate in (
        r"D:\Utilitarios\ffmpeg\bin\ffprobe.exe",
        r"C:\ffmpeg\bin\ffprobe.exe",
    ):
        if Path(candidate).is_file():
            return candidate
    return shutil.which("ffprobe")


def probe_duration(audio_path: Path, ffprobe_override: Optional[str] = None) -> Optional[float]:
    ffprobe = _find_ffprobe(ffprobe_override)
    if ffprobe:
        try:
            out = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(audio_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
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


# ---------------------------------------------------------------------------
# Decision log
# ---------------------------------------------------------------------------


def append_decision(
    decision_log_path: Path,
    selected: str,
    reason: str,
    options: list[dict[str, Any]],
    stage: str = "assets",
    user_approved: bool = True,
    confidence: float = 0.9,
) -> Optional[str]:
    """Append a voice_selection decision; never mutates previous entries."""
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
    decisions.append(
        {
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
        }
    )
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return new_id


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


class VoiceCraftTTS(BaseTool):
    name = "voice_craft_tts"
    version = "1.0.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "voicecraft"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["service:voicecraft@127.0.0.1:8090"]
    install_instructions = (
        "Start the VoiceCraft studio/API on port 8090:\n"
        "  D:\\Utilitarios\\VoiceCraft\\Iniciar API de Voz.bat\n"
        "Verify with: curl http://127.0.0.1:8090/health\n"
        "If it is offline, this tool falls back to tools/audio/piper_tts.py."
    )
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_catalog",
        "local_http_bridge",
        "piper_fallback",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "ssml": False,
        "emotion": True,
        "style_prompt": True,
    }
    best_for = [
        "expressive PT-BR narration through the local VoiceCraft studio",
        "reusing the principal configured VoiceCraft voice across scenes",
        "zero-cost narration with an automatic offline Piper fallback",
    ]
    not_good_for = [
        "true voice-clone matching (out of VoiceCraft's scope)",
        "fully offline runs (use piper_tts directly)",
        "guaranteed character-level deterministic output",
    ]

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=20)
    retry_policy = RetryPolicy(max_retries=1, backoff_seconds=1.0)
    idempotency_key_fields = ["text", "provider", "voice", "profile", "model", "instructions"]

    input_schema = {
        "type": "object",
        "required": ["text", "output_path"],
        "properties": {
            "text": {"type": "string"},
            "output_path": {"type": "string"},
            "language": {"type": "string", "default": "pt-BR"},
            "provider": {"type": "string", "default": "voicestudio"},
            "voice": {"type": ["string", "null"], "default": DEFAULT_VOICE},
            "profile": {"type": "string", "default": DEFAULT_PROFILE},
            "model": {"type": ["string", "null"], "default": None},
            "instructions": {"type": ["string", "null"], "default": None},
            "format": {"type": "string", "enum": ["wav", "mp3"], "default": "wav"},
            "rate": {"type": ["string", "number", "null"], "default": None},
            "pitch": {"type": ["string", "number", "null"], "default": None},
            "base_url": {"type": "string", "default": DEFAULT_BASE_URL},
            "voicestudio_url": {"type": "string", "default": DEFAULT_VOICESTUDIO_URL},
            "health_timeout": {"type": "number", "default": 12.0},
            "request_timeout": {"type": "number", "default": 180.0},
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
            "voice_used": {"type": ["string", "null"]},
            "model_used": {"type": ["string", "null"]},
            "profile_used": {"type": ["string", "null"]},
            "duration_seconds": {"type": ["number", "null"]},
            "fallback_used": {"type": "boolean"},
            "fallback_reason": {"type": ["string", "null"]},
            "decision_id": {"type": ["string", "null"]},
            "elapsed_seconds": {"type": "number"},
        },
    }

    def get_status(self) -> ToolStatus:
        """Cheap TCP probe (the /health catalog call takes ~5s)."""
        try:
            parsed = urllib.parse.urlsplit(DEFAULT_BASE_URL)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 8090
            with socket.create_connection((host, port), timeout=1.0):
                return ToolStatus.AVAILABLE
        except OSError:
            return ToolStatus.DEGRADED

    # -- execution ---------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        text = str(inputs.get("text") or "").strip()
        if not text:
            return ToolResult(success=False, error="text is required")

        out_path = Path(str(inputs.get("output_path") or "")).expanduser()
        if not out_path.is_absolute():
            out_path = Path.cwd() / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)

        base_url = str(inputs.get("base_url") or DEFAULT_BASE_URL)
        fallback_enabled = bool(inputs.get("fallback_to_piper", True))
        ffprobe_override = inputs.get("ffprobe")
        decision_log = inputs.get("decision_log")

        audio_bytes: Optional[bytes] = None
        headers: dict[str, str] = {}
        fallback_reason: Optional[str] = None
        fallback_used = False

        provider_in = str(inputs.get("provider") or "auto").strip().lower()
        vs_url = str(inputs.get("voicestudio_url") or DEFAULT_VOICESTUDIO_URL)
        direct_vs = provider_in == "voicestudio"

        if direct_vs:
            health = {"online": _port_open(vs_url), "detail": "direct VoiceStudio", "base_url": vs_url}
        else:
            health = health_check(base_url, timeout=float(inputs.get("health_timeout", 12.0)))

        if health["online"] and direct_vs:
            body = {
                "model": str(inputs.get("model") or "tts-1"),
                "voice": str(inputs.get("voice") or "").strip(),
                "input": text,
                "response_format": str(inputs.get("format") or "wav"),
                "language": "pt" if str(inputs.get("language") or "pt-BR").lower().startswith("pt") else str(inputs.get("language") or "pt"),
            }
            for key in ("instructions", "rate", "pitch"):
                value = inputs.get(key)
                if value not in (None, ""):
                    body[key] = value
            try:
                audio_bytes, headers = _post_voicestudio(
                    body, vs_url, timeout=float(inputs.get("request_timeout", 1800.0))
                )
                headers["x-tts-provider"] = "voicestudio"
                headers["x-tts-voice"] = str(body.get("voice") or "default")
                headers["x-tts-model"] = str(body.get("model"))
                headers["x-tts-profile"] = "cloned"
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="ignore")[:400]
                fallback_reason = f"VoiceStudio HTTP {exc.code}: {detail}"
            except Exception as exc:
                fallback_reason = f"VoiceStudio {type(exc).__name__}: {exc}"
        elif health["online"]:
            body: dict[str, Any] = {
                "text": text,
                "language": str(inputs.get("language") or "pt-BR"),
                "provider": str(inputs.get("provider") or "auto"),
                "profile": str(inputs.get("profile") or DEFAULT_PROFILE),
                "format": str(inputs.get("format") or "wav"),
            }
            for key in ("voice", "model", "instructions", "rate", "pitch"):
                value = inputs.get(key)
                if value not in (None, ""):
                    body[key] = value
            try:
                audio_bytes, headers = _post_tts(
                    body, base_url, timeout=float(inputs.get("request_timeout", 180.0))
                )
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="ignore")[:400]
                fallback_reason = f"VoiceCraft HTTP {exc.code}: {detail}"
            except Exception as exc:
                fallback_reason = f"{type(exc).__name__}: {exc}"
        else:
            fallback_reason = f"VoiceCraft offline ({health['detail']})"

        if audio_bytes is not None:
            tmp = out_path.with_suffix(out_path.suffix + ".part")
            tmp.write_bytes(audio_bytes)
            tmp.replace(out_path)
            provider_used = headers.get("x-tts-provider", "voicecraft")
            voice_used = headers.get("x-tts-voice")
            model_used = headers.get("x-tts-model") or inputs.get("model")
            profile_used = headers.get("x-tts-profile") or inputs.get("profile")
        else:
            if not fallback_enabled:
                return ToolResult(
                    success=False,
                    error=f"VoiceCraft unavailable and fallback disabled: {fallback_reason}",
                    data={"health": health, "fallback_reason": fallback_reason},
                )
            fallback_used = True
            fb = self._run_piper_fallback(inputs, text, out_path)
            if not fb.success:
                return ToolResult(
                    success=False,
                    error=f"VoiceCraft failed ({fallback_reason}) and Piper fallback failed ({fb.error})",
                    data={"health": health},
                )
            provider_used = "piper"
            voice_used = str(inputs.get("piper_model") or "pt_BR-faber-medium")
            model_used = voice_used
            profile_used = "piper-local"

        duration = probe_duration(out_path, ffprobe_override)
        decision_id = None
        if decision_log:
            options: list[dict[str, Any]] = []
            if not fallback_used:
                options.append(
                    {
                        "option_id": "voicecraft_principal",
                        "label": f"VoiceCraft principal voice ({provider_used}/{voice_used})",
                        "score": 0.94,
                        "reason": (
                            "Service online; reuses the principal configured voice with the "
                            "same provider/voice pinned across scenes for consistency."
                        ),
                    }
                )
            options.append(
                {
                    "option_id": "piper_local",
                    "label": f"Piper local ({voice_used if fallback_used else inputs.get('piper_model') or 'pt_BR-faber-medium'})",
                    "score": 0.6,
                    "reason": "Deterministic, fully offline, no quota or network dependency.",
                    "rejected_because": (
                        "VoiceCraft was offline or failed the request, so the local fallback took over."
                        if fallback_used
                        else "Lower naturalness and no emotional control; kept only as the offline fallback."
                    ),
                }
            )
            reason = str(inputs.get("decision_reason") or "").strip()
            if not reason:
                reason = (
                    f"VoiceCraft {'fallback to Piper' if fallback_used else 'principal voice'} used for narration; "
                    f"voice={voice_used}, profile={profile_used or 'n/a'}."
                )
            decision_id = append_decision(
                Path(decision_log),
                selected="piper_local" if fallback_used else "voicecraft_principal",
                reason=reason,
                options=options,
                stage=str(inputs.get("stage") or "assets"),
            )

        return ToolResult(
            success=True,
            data={
                "audio_path": str(out_path),
                "provider_used": provider_used,
                "voice_used": voice_used,
                "model_used": model_used,
                "profile_used": profile_used,
                "duration_seconds": duration,
                "fallback_used": fallback_used,
                "fallback_reason": fallback_reason,
                "decision_id": decision_id,
                "elapsed_seconds": round(time.time() - started, 2),
            },
        )

    # -- fallback ----------------------------------------------------------

    def _run_piper_fallback(
        self, inputs: dict[str, Any], text: str, out_path: Path
    ) -> ToolResult:
        try:
            from tools.audio.piper_tts import PiperTTS

            piper = PiperTTS()
            result = piper.execute(
                {
                    "text": text,
                    "output_path": str(out_path),
                    "model": inputs.get("piper_model") or "pt_BR-faber-medium",
                    "length_scale": float(inputs.get("piper_length_scale") or 0.85),
                }
            )
            return result
        except Exception as exc:
            return ToolResult(success=False, error=f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cli() -> int:
    parser = argparse.ArgumentParser(description="VoiceCraft TTS client (port 8090)")
    parser.add_argument("--text", help="Text to synthesize")
    parser.add_argument("--text-file", help="Read the text from a file instead")
    parser.add_argument("--out", required=False, help="Output audio path")
    parser.add_argument("--provider", default="voicestudio")
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--voicestudio-url", default=DEFAULT_VOICESTUDIO_URL)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--model", default=None)
    parser.add_argument("--instructions", default=None)
    parser.add_argument("--language", default="pt-BR")
    parser.add_argument("--format", default="wav", choices=["wav", "mp3"])
    parser.add_argument("--decision-log", default=None)
    parser.add_argument("--health", action="store_true", help="Only report service health")
    parser.add_argument("--list-voices", action="store_true", help="List voices for --provider")
    args = parser.parse_args()

    if args.health:
        print(json.dumps(health_check(), indent=2, ensure_ascii=False))
        return 0
    if args.list_voices:
        print(json.dumps(list_voices(args.provider, args.language), indent=2, ensure_ascii=False))
        return 0
    if not args.out:
        parser.error("--out is required for synthesis")

    text = args.text
    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8")
    if not text:
        parser.error("--text or --text-file is required")

    tool = VoiceCraftTTS()
    result = tool.execute(
        {
            "text": text,
            "output_path": args.out,
            "provider": args.provider,
            "voice": args.voice,
            "profile": args.profile,
            "model": args.model,
            "instructions": args.instructions,
            "language": args.language,
            "format": args.format,
            "voicestudio_url": args.voicestudio_url,
            "decision_log": args.decision_log,
        }
    )
    print(json.dumps(dataclasses.asdict(result), indent=2, ensure_ascii=False, default=str))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
