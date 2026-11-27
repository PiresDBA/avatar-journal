"""AI Editorial Intelligence (Editor-Chefe) package for avatar-journal."""

from .programs import PROGRAMS, VALID_PROGRAMS, get_program, list_programs
from .memory_store import (
    VALID_STATES,
    STATE_TRANSITIONS,
    EditorialMemoryStore,
)

__all__ = [
    "PROGRAMS",
    "VALID_PROGRAMS",
    "VALID_STATES",
    "STATE_TRANSITIONS",
    "EditorialMemoryStore",
    "get_program",
    "list_programs",
]
