"""Install PC-side reverse-engineering tools: jadx, apktool, scrcpy.

Assumes an apt-based distro with these packages available (Kali does; the
original script made the same assumption). Homebrew is supported as a
secondary path for macOS users.
"""
from __future__ import annotations

import platform
import shutil

from .shell import run

TOOLS = ("jadx", "apktool", "scrcpy")


def missing_tools() -> list[str]:
    return [tool for tool in TOOLS if shutil.which(tool) is None]


def install_missing() -> list[str]:
    """Install whatever's missing from TOOLS. Returns what's still missing afterward."""
    missing = missing_tools()
    if not missing:
        return []

    system = platform.system()
    if system == "Linux" and shutil.which("apt-get"):
        cmd = ["apt-get", "install", "-y", *missing]
        run(["sudo", *cmd] if shutil.which("sudo") else cmd, timeout=300)
    elif system == "Darwin" and shutil.which("brew"):
        run(["brew", "install", *missing], timeout=300)
    else:
        raise RuntimeError(
            f"Don't know how to install {missing} automatically on {system}. "
            "Install them manually and re-run."
        )
    return missing_tools()
