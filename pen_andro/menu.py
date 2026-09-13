"""Interactive terminal menu — the classic numbered-option UI from the
original script, rebuilt on top of the Phase 2 modules instead of
duplicating their logic."""
from __future__ import annotations

from rich.markup import escape

from . import adb as adb_mod
from . import android_apps, frida_tools, network, pc_tools
from . import burp as burp_mod
from .config import Config

BANNER = r"""
 ____             _              _
|  _ \ ___ _ __   / \   _ __   __| |_ __ ___
| |_) / _ \ '_ \ / _ \ | '_ \ / _` | '__/ _ \
|  __/  __/ | | / ___ \| | | | (_| | | | (_) |
|_|   \___|_| |_/_/   \_\_| |_|\__,_|_|  \___/
"""

MENU = """
1. All
2. Move Burp Suite certificate to the device
3. PC tools (jadx, apktool, scrcpy, frida, objection)
4. Android Frida server
5. Check/fix Frida version mismatch
6. Android apps (ProxyToggle, ProxyDroid, ADB WiFi)
0. Exit
"""


def _require_device(serial, console):
    device = adb_mod.resolve_device(serial)
    console.print(f"[green]adb connected:[/] {device.serial}")
    if not adb_mod.check_root(device.serial):
        console.print("[red]Root access denied. Grant root to adb from the on-device superuser manager and retry.[/]")
        raise SystemExit(1)
    return device.serial


def _run_all(cfg: Config, console):
    if not network.has_internet():
        console.print("[red]No internet connectivity.[/]")
        return
    serial = _require_device(cfg.device_serial, console)
    pc_tools.install_missing()
    frida_tools.install_pc_tools()
    console.print(android_apps.install_all(serial, cfg.workdir))
    frida_tools.ensure_frida_server(serial, cfg.workdir, prefer_magisk=cfg.prefer_magisk)
    if burp_mod.is_burp_running(cfg.burp.host, cfg.burp.port):
        try:
            name = burp_mod.install_certificate(serial, cfg.burp.host, cfg.burp.port, cfg.workdir)
            console.print(f"[green]Certificate installed: {name}[/]")
        except burp_mod.BurpError as exc:
            console.print(f"[yellow]{escape(str(exc))}[/]")
    else:
        console.print(f"[yellow]Skipping certificate: Burp not reachable at {cfg.burp.host}:{cfg.burp.port}[/]")
    console.print("[bold green]Done. Reboot the device to apply all changes.[/]")


def _run_cert(cfg: Config, console):
    if not network.has_internet():
        console.print("[red]No internet connectivity.[/]")
        return
    serial = _require_device(cfg.device_serial, console)
    if not burp_mod.is_burp_running(cfg.burp.host, cfg.burp.port):
        console.print(f"[red]Burp not reachable at {cfg.burp.host}:{cfg.burp.port}[/]")
        return
    try:
        name = burp_mod.install_certificate(serial, cfg.burp.host, cfg.burp.port, cfg.workdir, force=True)
        console.print(f"[green]Installed {name}. Reboot to apply.[/]")
    except burp_mod.BurpError as exc:
        console.print(f"[yellow]{exc}[/]")


def _run_pc_tools(console):
    still_missing = pc_tools.install_missing()
    if still_missing:
        console.print(f"[red]Could not install: {still_missing}[/]")
    else:
        console.print("[green]jadx, apktool, scrcpy ready.[/]")
    frida_tools.install_pc_tools()
    console.print("[green]frida & objection ready.[/]")


def _run_frida_server(cfg: Config, console):
    if not network.has_internet():
        console.print("[red]No internet connectivity.[/]")
        return
    serial = _require_device(cfg.device_serial, console)
    version = frida_tools.ensure_frida_server(serial, cfg.workdir, prefer_magisk=cfg.prefer_magisk)
    console.print(f"[green]frida-server ready (version {version}).[/]")


def _run_frida_check(cfg: Config, console):
    serial = _require_device(cfg.device_serial, console)
    console.print(frida_tools.check_version_mismatch(serial))


def _run_apps(cfg: Config, console):
    if not network.has_internet():
        console.print("[red]No internet connectivity.[/]")
        return
    serial = _require_device(cfg.device_serial, console)
    for name, status in android_apps.install_all(serial, cfg.workdir).items():
        console.print(f"{name}: {status}")


_ACTIONS = {
    "1": _run_all,
    "2": _run_cert,
    "4": _run_frida_server,
    "5": _run_frida_check,
    "6": _run_apps,
}


def interactive_menu(cfg: Config, console):
    cfg.workdir.mkdir(parents=True, exist_ok=True)

    while True:
        console.print(BANNER, style="cyan")
        console.print(MENU)
        choice = console.input("I want to install: ").strip()

        try:
            if choice == "3":
                _run_pc_tools(console)
            elif choice == "0":
                console.print("Bye!")
                return
            elif choice in _ACTIONS:
                _ACTIONS[choice](cfg, console)
            else:
                console.print("[yellow]Unknown option.[/]")
        except SystemExit:
            continue
        except Exception as exc:  # keep the menu alive on a single failed action
            console.print(f"[red]Error: {escape(str(exc))}[/]")
