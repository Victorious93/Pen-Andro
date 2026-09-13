"""Command-line interface for pen-andro.

Running `pen-andro` with no subcommand drops into the classic interactive
menu (see menu.py); each subcommand below is the same functionality wired
up for scripting/CI use.
"""
from __future__ import annotations

import logging
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

from . import adb as adb_mod
from . import android_apps, frida_tools, network, pc_tools
from . import burp as burp_mod
from .config import Config, load_config

console = Console()


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_time=False, show_path=False)],
    )


def _prepare_workdir(cfg: Config) -> Path:
    cfg.workdir.mkdir(parents=True, exist_ok=True)
    return cfg.workdir


def _require_device(serial: str | None) -> str:
    device = adb_mod.resolve_device(serial)
    console.print(f"[green]adb connected:[/] {device.serial}")
    if not adb_mod.check_root(device.serial):
        console.print(
            "[red]Root access denied.[/] Grant root to adb from the on-device "
            "superuser manager (Magisk, etc.) and try again."
        )
        raise SystemExit(1)
    return device.serial


def _require_internet() -> None:
    if not network.has_internet():
        console.print("[red]No internet connectivity detected.[/]")
        raise SystemExit(1)


@click.group(invoke_without_command=True)
@click.option("--config", "config_path", default=None, help="Path to config.yaml")
@click.option("--device", default=None, help="ADB device serial (overrides config)")
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging")
@click.pass_context
def cli(ctx, config_path, device, verbose):
    """Pen-Andro: Android pentesting environment setup."""
    _setup_logging(verbose)
    cfg = load_config(config_path)
    if device:
        cfg.device_serial = device
    ctx.obj = cfg
    if ctx.invoked_subcommand is None:
        from .menu import interactive_menu

        interactive_menu(cfg, console)


@cli.command()
@click.pass_obj
def doctor(cfg: Config):
    """Check preconditions: internet, Burp proxy, adb, root."""
    _require_internet()
    console.print("[green]Internet: OK[/]")

    if burp_mod.is_burp_running(cfg.burp.host, cfg.burp.port):
        console.print(f"[green]Burp Suite reachable at {cfg.burp.host}:{cfg.burp.port}[/]")
    else:
        console.print(f"[yellow]Burp Suite not reachable at {cfg.burp.host}:{cfg.burp.port}[/]")

    try:
        serial = _require_device(cfg.device_serial)
        console.print(f"[green]Device ready: {serial} (root OK)[/]")
    except SystemExit:
        pass


@cli.command()
@click.option("--force", is_flag=True, help="Replace an existing certificate")
@click.pass_obj
def cert(cfg: Config, force: bool):
    """Install the Burp Suite CA certificate onto the device."""
    _require_internet()
    serial = _require_device(cfg.device_serial)
    workdir = _prepare_workdir(cfg)
    if not burp_mod.is_burp_running(cfg.burp.host, cfg.burp.port):
        console.print(f"[red]Burp Suite is not reachable at {cfg.burp.host}:{cfg.burp.port}[/]")
        raise SystemExit(1)
    try:
        name = burp_mod.install_certificate(serial, cfg.burp.host, cfg.burp.port, workdir, force=force)
        console.print(f"[green]Certificate installed: {name}. Reboot the device to apply.[/]")
    except burp_mod.BurpError as exc:
        console.print(f"[yellow]{exc}[/]")


@cli.command("pc-tools")
def pc_tools_cmd():
    """Install/verify PC-side tools: jadx, apktool, scrcpy, frida, objection."""
    still_missing = pc_tools.install_missing()
    if still_missing:
        console.print(f"[red]Could not install: {still_missing}[/]")
    else:
        console.print("[green]jadx, apktool, scrcpy ready.[/]")

    installed = frida_tools.install_pc_tools()
    console.print(
        "[green]frida & objection installed.[/]"
        if installed
        else "[green]frida & objection already present.[/]"
    )


@cli.command("frida-server")
@click.option("--force", is_flag=True, help="Reinstall even if already present")
@click.pass_obj
def frida_server_cmd(cfg: Config, force: bool):
    """Install/upgrade frida-server on the connected device."""
    _require_internet()
    serial = _require_device(cfg.device_serial)
    workdir = _prepare_workdir(cfg)
    version = frida_tools.ensure_frida_server(serial, workdir, prefer_magisk=cfg.prefer_magisk, force=force)
    console.print(f"[green]frida-server ready (version {version}).[/]")


@cli.command("frida-check")
@click.pass_obj
def frida_check_cmd(cfg: Config):
    """Compare Frida versions across latest release, PC, and device."""
    serial = _require_device(cfg.device_serial)
    info = frida_tools.check_version_mismatch(serial)
    console.print(info)
    if not info["in_sync"]:
        console.print("[yellow]Versions differ; run 'pen-andro frida-server --force' or upgrade the PC package.[/]")


@cli.command("apps")
@click.pass_obj
def apps_cmd(cfg: Config):
    """Install helper Android apps (ProxyToggle, ProxyDroid, ADB WiFi)."""
    _require_internet()
    serial = _require_device(cfg.device_serial)
    workdir = _prepare_workdir(cfg)
    for name, status in android_apps.install_all(serial, workdir).items():
        console.print(f"{name}: {status}")


@cli.command("all")
@click.option("--force-frida", is_flag=True, help="Reinstall frida-server even if present")
@click.pass_obj
def all_cmd(cfg: Config, force_frida: bool):
    """Run the full setup: connectivity, root, PC tools, apps, Frida, and cert."""
    _require_internet()
    serial = _require_device(cfg.device_serial)
    workdir = _prepare_workdir(cfg)

    pc_tools.install_missing()
    frida_tools.install_pc_tools()
    for name, status in android_apps.install_all(serial, workdir).items():
        console.print(f"{name}: {status}")
    version = frida_tools.ensure_frida_server(serial, workdir, prefer_magisk=cfg.prefer_magisk, force=force_frida)
    console.print(f"[green]frida-server ready (version {version}).[/]")

    if burp_mod.is_burp_running(cfg.burp.host, cfg.burp.port):
        try:
            name = burp_mod.install_certificate(serial, cfg.burp.host, cfg.burp.port, workdir)
            console.print(f"[green]Certificate installed: {name}[/]")
        except burp_mod.BurpError as exc:
            console.print(f"[yellow]{exc}[/]")
    else:
        console.print(f"[yellow]Skipping certificate install: Burp not reachable at {cfg.burp.host}:{cfg.burp.port}[/]")

    console.print("[bold green]Setup complete. Reboot the device to apply all changes.[/]")


def main():
    cli()


if __name__ == "__main__":
    main()
