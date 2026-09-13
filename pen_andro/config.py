"""Configuration loading: config.yaml file with environment-variable overrides.

Replaces the original script's hardcoded `127.0.0.1:8080` and single-device
assumption.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATHS = [
    Path("config.yaml"),
    Path.home() / ".config" / "pen-andro" / "config.yaml",
]


@dataclass
class BurpConfig:
    host: str = "127.0.0.1"
    port: int = 8080


@dataclass
class Config:
    burp: BurpConfig = field(default_factory=BurpConfig)
    device_serial: str | None = None
    prefer_magisk: bool = True
    workdir: Path = field(default_factory=lambda: Path("/tmp/pen_andro"))
    pinned_frida_version: str | None = None


def load_config(path: str | None = None) -> Config:
    candidates = [Path(path)] if path else DEFAULT_CONFIG_PATHS
    data: dict = {}
    for candidate in candidates:
        if candidate.is_file():
            data = yaml.safe_load(candidate.read_text()) or {}
            break

    burp_data = data.get("burp") or {}
    return Config(
        burp=BurpConfig(
            host=os.environ.get("PEN_ANDRO_BURP_HOST", burp_data.get("host", "127.0.0.1")),
            port=int(os.environ.get("PEN_ANDRO_BURP_PORT", burp_data.get("port", 8080))),
        ),
        device_serial=os.environ.get("PEN_ANDRO_DEVICE", data.get("device_serial")),
        prefer_magisk=bool(data.get("prefer_magisk", True)),
        workdir=Path(data.get("workdir", "/tmp/pen_andro")),
        pinned_frida_version=data.get("pinned_frida_version"),
    )
