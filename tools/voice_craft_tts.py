"""Compatibility shim forwarding legacy `voice_craft_tts` imports to `tools.voicestudio_tts`.

VoiceCraft (:8090) was retired in favor of the official VoiceStudio CLI (`voicestudio.exe`)
and direct HTTP API (`:3900`). Update callers to `tools/voicestudio_tts.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.voicestudio_tts import (  # noqa: F401
    DEFAULT_ENGINE,
    DEFAULT_VOICE,
    DEFAULT_VOICESTUDIO_URL,
    ENGINE_SPECS,
    ENGINE_TAGS,
    OMNIVOICE_TAGS_WHITELIST,
    VoiceStudioTTS,
    _cli,
    analyze_expression,
    flush_memory,
    health_check,
    probe_duration,
    validate_instruct,
)

VoiceCraftTTS = VoiceStudioTTS

if __name__ == "__main__":
    raise SystemExit(_cli())
