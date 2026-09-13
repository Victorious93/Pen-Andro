"""Frida server management: install, version matching, Magisk module support."""
from __future__ import annotations

import lzma
import shutil
from pathlib import Path

import requests

from . import adb as adb_mod
from .shell import run

ARCH_MAP = {
    "x86_64": "x86_64",
    "x86": "x86",
    "arm64-v8a": "arm64",
    "armeabi-v7a": "arm",
    "armeabi": "arm",
}


class FridaError(RuntimeError):
    pass


def latest_frida_version() -> str:
    response = requests.get(
        "https://api.github.com/repos/frida/frida/releases/latest", timeout=10
    )
    response.raise_for_status()
    return response.json()["tag_name"].lstrip("v")


def pc_frida_version() -> str | None:
    result = run(["frida", "--version"])
    return result.stdout.strip() if result.ok and result.stdout.strip() else None


def android_frida_version(serial: str) -> str | None:
    version = adb_mod.shell(serial, "frida-server --version").stdout.strip()
    return version or None


def device_arch(serial: str) -> str:
    abi = adb_mod.get_cpu_abi(serial)
    for prefix, arch in ARCH_MAP.items():
        if abi.startswith(prefix):
            return arch
    raise FridaError(f"Unrecognized Android CPU ABI: {abi!r}")


def install_pc_tools() -> bool:
    """Install frida-tools & objection via pip if missing. Returns True if newly installed."""
    if run(["python3", "-c", "import frida, objection"]).ok:
        return False
    run(["pip3", "install", "--upgrade", "frida", "frida-tools", "objection"], timeout=180)
    return True


def _download(url: str, dest: Path) -> None:
    response = requests.get(url, stream=True, timeout=60)
    if response.status_code == 404:
        raise FridaError(f"Nothing found at {url}")
    response.raise_for_status()
    with open(dest, "wb") as handle:
        for chunk in response.iter_content(chunk_size=1 << 16):
            handle.write(chunk)


def download_frida_server(workdir: Path, arch: str, version: str) -> Path:
    url = (
        f"https://github.com/frida/frida/releases/download/{version}/"
        f"frida-server-{version}-android-{arch}.xz"
    )
    xz_path = workdir / "frida-server.xz"
    _download(url, xz_path)

    server_path = workdir / "frida-server"
    with lzma.open(xz_path) as src, open(server_path, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return server_path


def install_frida_server_manual(serial: str, workdir: Path, version: str | None = None) -> str:
    workdir.mkdir(parents=True, exist_ok=True)
    arch = device_arch(serial)
    version = version or latest_frida_version()
    server_path = download_frida_server(workdir, arch, version)

    push = adb_mod.adb(serial, "push", str(server_path), "/data/local/tmp/")
    if not push.ok:
        raise FridaError(f"push failed: {push.stderr}")
    adb_mod.shell(serial, "chmod 755 /data/local/tmp/frida-server", as_root=True)
    adb_mod.remount_system(serial)
    move = adb_mod.shell(
        serial, "mv /data/local/tmp/frida-server /system/xbin/frida-server", as_root=True
    )
    if not move.ok:
        raise FridaError(f"Could not install frida-server to /system/xbin: {move.stderr}")
    return version


def is_magisk_available(serial: str) -> bool:
    result = adb_mod.shell(serial, "magisk -v")
    return result.ok and "MAGISK" in result.stdout.upper()


def install_magisk_frida_module(serial: str, workdir: Path) -> str:
    workdir.mkdir(parents=True, exist_ok=True)
    response = requests.get(
        "https://api.github.com/repos/ViRb3/magisk-frida/releases/latest", timeout=10
    )
    response.raise_for_status()
    version = response.json()["tag_name"].lstrip("v")
    asset_url = (
        f"https://github.com/ViRb3/magisk-frida/releases/download/"
        f"{version}/MagiskFrida-{version}.zip"
    )

    module_path = workdir / "frida_module.zip"
    _download(asset_url, module_path)

    push = adb_mod.adb(serial, "push", str(module_path), "/data/local/tmp/")
    if not push.ok:
        raise FridaError(f"push failed: {push.stderr}")
    install = adb_mod.shell(
        serial,
        "magisk --install-module /data/local/tmp/frida_module.zip",
        as_root=True,
        timeout=120,
    )
    if not install.ok:
        raise FridaError(f"Magisk module install failed: {install.stderr}")

    trust_url = (
        "https://github.com/NVISOsecurity/MagiskTrustUserCerts/releases/"
        "download/v0.4.1/AlwaysTrustUserCerts.zip"
    )
    trust_path = workdir / "trust_module.zip"
    _download(trust_url, trust_path)
    adb_mod.adb(serial, "push", str(trust_path), "/data/local/tmp/")
    adb_mod.shell(
        serial,
        "magisk --install-module /data/local/tmp/trust_module.zip",
        as_root=True,
        timeout=120,
    )
    return version


def ensure_frida_server(
    serial: str, workdir: Path, *, prefer_magisk: bool = True, force: bool = False
) -> str:
    """Ensure frida-server is installed on-device. Returns the resulting version."""
    current = android_frida_version(serial)
    if current and not force:
        return current

    if prefer_magisk and is_magisk_available(serial):
        return install_magisk_frida_module(serial, workdir)
    return install_frida_server_manual(serial, workdir)


def check_version_mismatch(serial: str) -> dict:
    pc = pc_frida_version()
    android = android_frida_version(serial)
    return {
        "latest": latest_frida_version(),
        "pc": pc,
        "android": android,
        "in_sync": pc == android,
    }
