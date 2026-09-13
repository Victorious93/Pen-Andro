"""Basic connectivity check."""
from __future__ import annotations

from .shell import run


def has_internet(host: str = "8.8.8.8") -> bool:
    return run(["ping", "-c", "1", "-W", "2", host], timeout=5).ok
