"""Install helper Android apps: ProxyToggle, ADB WiFi, ProxyDroid.

ADB WiFi and ProxyDroid ship as APKs already vendored under `assets/` in
this repository, so those two install from the local file instead of
re-downloading from a third-party mirror repo, unlike the original script.
ProxyToggle has no local copy, so it's fetched from its upstream release
(a zip containing `proxy-toggle.apk`, same as upstream distributes it).
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import requests

from . import adb as adb_mod

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


@dataclass
class AndroidApp:
    name: str
    package: str
    source_type: str  # "local" or "zip"
    source: str  # local path (relative to ASSETS_DIR) or a URL
    archive_apk_name: str | None = None  # required when source_type == "zip"
    grant_permissions: tuple[str, ...] = field(default_factory=tuple)


APPS = [
    AndroidApp(
        name="ProxyToggle",
        package="com.kinandcarta.create.proxytoggle",
        source_type="zip",
        source=(
            "https://github.com/theappbusiness/android-proxy-toggle/releases/"
            "download/v1.0.1/Proxy.Toggle.v1.0.1.zip"
        ),
        archive_apk_name="proxy-toggle.apk",
        grant_permissions=("android.permission.WRITE_SECURE_SETTINGS",),
    ),
    AndroidApp(
        name="ADB WiFi",
        package="com.sujanpoudel.adbwifi",
        source_type="local",
        source="adb_wifi.apk",
    ),
    AndroidApp(
        name="ProxyDroid",
        package="org.proxydroid",
        source_type="local",
        source="org.proxydroid.apk",
    ),
]


def is_installed(serial: str, package: str) -> bool:
    result = adb_mod.shell(serial, "pm list packages -3")
    return f"package:{package}" in result.stdout


def _resolve_apk(app: AndroidApp, workdir: Path) -> Path:
    if app.source_type == "local":
        return ASSETS_DIR / app.source

    if app.source_type == "zip":
        zip_path = workdir / f"{app.package}.zip"
        response = requests.get(app.source, timeout=60)
        response.raise_for_status()
        zip_path.write_bytes(response.content)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extract(app.archive_apk_name, path=workdir)
        return workdir / app.archive_apk_name

    raise ValueError(f"Unknown source_type: {app.source_type}")


def install_app(serial: str, app: AndroidApp, workdir: Path) -> bool:
    """Returns True if newly installed, False if already present."""
    if is_installed(serial, app.package):
        return False

    workdir.mkdir(parents=True, exist_ok=True)
    apk_path = _resolve_apk(app, workdir)

    install = adb_mod.adb(serial, "install", "-t", "-r", str(apk_path))
    if not install.ok:
        raise RuntimeError(f"Failed to install {app.name}: {install.stderr}")

    for permission in app.grant_permissions:
        adb_mod.adb(serial, "shell", "pm", "grant", app.package, permission)
    return True


def install_all(serial: str, workdir: Path) -> dict[str, str]:
    results = {}
    for app in APPS:
        try:
            results[app.name] = "installed" if install_app(serial, app, workdir) else "already installed"
        except Exception as exc:  # surfaced to the caller per-app, not fatal for the batch
            results[app.name] = f"failed: {exc}"
    return results
