"""Burp Suite proxy detection and CA certificate installation onto a device.

Mirrors the cert-hashing dance from the original script (Android's system
trust store expects the file named after the certificate's old-style
subject hash, e.g. `9a5ba575.0`), but does the OpenSSL work through
subprocess with explicit argument lists instead of shelling out to a chain
of piped commands.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import requests

from . import adb as adb_mod


class BurpError(RuntimeError):
    pass


def is_burp_running(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        response = requests.get(f"http://{host}:{port}/", timeout=timeout)
    except requests.RequestException:
        return False
    return "Burp" in response.text


def install_certificate(
    serial: str, host: str, port: int, workdir: Path, *, force: bool = False
) -> str:
    """Install Burp's CA certificate into the device's system trust store.

    Returns the installed certificate's filename. Raises BurpError if a
    certificate is already installed (unless force=True) or any step fails.
    """
    check = adb_mod.shell(
        serial, "ls /system/etc/security/cacerts | grep 9a5ba575.0", as_root=True
    )
    if "9a5ba575.0" in check.stdout and not force:
        raise BurpError(
            "A Burp certificate is already installed; pass force=True to replace it."
        )

    workdir.mkdir(parents=True, exist_ok=True)
    der_path = workdir / "burp_cacert.der"
    response = requests.get(f"http://{host}:{port}/cert", timeout=10)
    response.raise_for_status()
    der_path.write_bytes(response.content)

    pem_path = workdir / "burp_cacert.pem"
    subprocess.run(
        ["openssl", "x509", "-inform", "DER", "-in", str(der_path), "-out", str(pem_path)],
        check=True,
        capture_output=True,
    )
    hash_proc = subprocess.run(
        ["openssl", "x509", "-inform", "PEM", "-subject_hash_old", "-in", str(pem_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    cert_hash = hash_proc.stdout.splitlines()[0].strip()
    cert_name = f"{cert_hash}.0"
    named_path = workdir / cert_name
    named_path.write_bytes(pem_path.read_bytes())

    push = adb_mod.adb(serial, "push", str(named_path), "/sdcard/")
    if not push.ok:
        raise BurpError(f"adb push failed: {push.stderr}")

    adb_mod.remount_system(serial)
    move = adb_mod.shell(
        serial, f"mv /sdcard/{cert_name} /system/etc/security/cacerts/", as_root=True
    )
    if not move.ok:
        raise BurpError(f"Failed to move certificate into place: {move.stderr}")
    adb_mod.shell(serial, f"chmod 644 /system/etc/security/cacerts/{cert_name}", as_root=True)

    return cert_name
