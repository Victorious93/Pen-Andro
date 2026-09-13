"""ADB device discovery, root checks, and command execution.

Every other module talks to the device only through this module, and always
via `adb -s <serial> ...` so multiple connected devices are unambiguous
(the original Bash script refused to run at all if more than one device was
attached).
"""
from __future__ import annotations

from dataclasses import dataclass

from .shell import run


class AdbError(RuntimeError):
    pass


@dataclass(frozen=True)
class Device:
    serial: str
    state: str


def list_devices() -> list[Device]:
    result = run(["adb", "devices"])
    devices = []
    for line in result.stdout.splitlines()[1:]:
        line = line.strip()
        if not line or "\t" not in line:
            continue
        serial, state = line.split("\t")
        devices.append(Device(serial, state))
    return devices


def resolve_device(serial: str | None = None) -> Device:
    """Pick the device to operate on.

    Raises AdbError if none are connected, if a requested serial isn't
    present, or if more than one is connected and no serial was given.
    """
    online = [d for d in list_devices() if d.state == "device"]
    if not online:
        raise AdbError(
            "No ADB device found. Connect a rooted device/emulator with USB "
            "debugging enabled and authorized for this computer."
        )
    if serial:
        for device in online:
            if device.serial == serial:
                return device
        raise AdbError(
            f"Device '{serial}' not found among connected devices: "
            f"{[d.serial for d in online]}"
        )
    if len(online) > 1:
        raise AdbError(
            "Multiple devices connected: "
            f"{[d.serial for d in online]}. Pass --device <serial> or set "
            "device_serial in config.yaml to pick one."
        )
    return online[0]


def adb(serial: str, *args: str, timeout: int = 30):
    return run(["adb", "-s", serial, *args], timeout=timeout)


def shell(serial: str, command: str, *, as_root: bool = False, timeout: int = 30):
    if as_root:
        command = f"su -c '{command}'"
    return run(["adb", "-s", serial, "shell", command], timeout=timeout)


def check_root(serial: str) -> bool:
    result = shell(serial, "echo ok", as_root=True, timeout=15)
    return result.ok and "ok" in result.stdout


def get_cpu_abi(serial: str) -> str:
    return shell(serial, "getprop ro.product.cpu.abi").stdout.strip()


def remount_system(serial: str) -> None:
    result = adb(serial, "remount")
    if not result.ok:
        shell(serial, "mount -o rw,remount /", as_root=True)
