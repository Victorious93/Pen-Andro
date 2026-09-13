"""Subprocess wrapper used by every other module.

Commands are always passed as argument lists (never `shell=True`), so
user-controlled values such as a Burp host:port entered at a prompt cannot
be interpreted by a shell.
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger("pen_andro")


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run(cmd: list[str], *, check: bool = False, timeout: int = 30) -> CommandResult:
    logger.debug("running: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        return CommandResult(127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        return CommandResult(124, "", f"timed out after {timeout}s: {exc}")

    result = CommandResult(proc.returncode, proc.stdout, proc.stderr)
    if check and not result.ok:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr}")
    return result
