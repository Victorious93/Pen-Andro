"""Command-line interface for pen-andro.

Running `pen-andro` with no subcommand drops into the classic interactive
menu (see menu.py); each subcommand below is the same functionality wired
up for scripting/CI use, with multi-device fan-out via `--device all`.
"""
from __future__ import annotations

import logging
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.logging import RichHandler
from rich.markup import escape

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


def _require_devices(serial: str | None) -> list[str]:
    """Resolve to one or more rooted device serials (supports --device all).

    Devices that fail the root check are skipped with a warning rather than
    aborting the whole run, so `--device all` still proceeds on the
    devices that are usable.
    """
    try:
        devices = adb_mod.resolve_devices(serial)
    except adb_mod.AdbError as exc:
        console.print(f"[red]{escape(str(exc))}[/]")
        raise SystemExit(1) from exc

    ready = []
    for device in devices:
        console.print(f"[green]adb connected:[/] {device.serial}")
        if adb_mod.check_root(device.serial):
            ready.append(device.serial)
        else:
            console.print(f"[yellow]{device.serial}: root access denied, skipping.[/]")

    if not ready:
        console.print(
            "[red]No device with root access available.[/] Grant root to adb "
            "from the on-device superuser manager (Magisk, etc.) and retry."
        )
        raise SystemExit(1)
    return ready


def _require_internet() -> None:
    if not network.has_internet():
        console.print("[red]No internet connectivity detected.[/]")
        raise SystemExit(1)


@click.group(invoke_without_command=True)
@click.option("--config", "config_path", default=None, help="Path to config.yaml")
@click.option(
    "--device",
    default=None,
    help="ADB device serial, or 'all' to fan out across every connected device (overrides config)",
)
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
    """Check preconditions: internet, Burp proxy, adb, root (per matched device)."""
    _require_internet()
    console.print("[green]Internet: OK[/]")

    if burp_mod.is_burp_running(cfg.burp.host, cfg.burp.port):
        console.print(f"[green]Burp Suite reachable at {cfg.burp.host}:{cfg.burp.port}[/]")
    else:
        console.print(f"[yellow]Burp Suite not reachable at {cfg.burp.host}:{cfg.burp.port}[/]")

    try:
        devices = adb_mod.resolve_devices(cfg.device_serial)
    except adb_mod.AdbError as exc:
        console.print(f"[red]{escape(str(exc))}[/]")
        return

    for device in devices:
        status = "[green]root OK[/]" if adb_mod.check_root(device.serial) else "[red]root denied[/]"
        console.print(f"{device.serial}: {status}")


@cli.command()
def init():
    """Interactively write config.yaml (Burp host/port, device, Magisk preference)."""
    console.print("[bold]Pen-Andro configuration wizard[/]")

    host = click.prompt("Burp Suite proxy host", default="127.0.0.1")
    port = click.prompt("Burp Suite proxy port", default=8080, type=int)

    online = [d.serial for d in adb_mod.list_devices() if d.state == "device"]
    device_serial = None
    if len(online) > 1:
        console.print(f"Multiple devices detected: {escape(str(online))}")
        device_serial = (
            click.prompt(
                "Default device serial ('all' to always fan out, blank to choose each time)",
                default="",
                show_default=False,
            )
            or None
        )
    elif online:
        console.print(f"Detected device: {online[0]}")

    prefer_magisk = click.confirm(
        "Prefer installing Frida as a Magisk module when available?", default=True
    )
    workdir = click.prompt("Scratch working directory", default="/tmp/pen_andro")

    config_path = Path("config.yaml")
    if config_path.exists() and not click.confirm(f"{config_path} already exists. Overwrite?", default=False):
        console.print("Aborted; config.yaml left unchanged.")
        return

    data = {
        "burp": {"host": host, "port": port},
        "device_serial": device_serial,
        "prefer_magisk": prefer_magisk,
        "workdir": workdir,
        "pinned_frida_version": None,
    }
    config_path.write_text(yaml.safe_dump(data, sort_keys=False))
    console.print(f"[green]Wrote {config_path}[/]")


@cli.command()
@click.option("--force", is_flag=True, help="Replace an existing certificate")
@click.pass_obj
def cert(cfg: Config, force: bool):
    """Install the Burp Suite CA certificate onto the device(s)."""
    _require_internet()
    if not burp_mod.is_burp_running(cfg.burp.host, cfg.burp.port):
        console.print(f"[red]Burp Suite is not reachable at {cfg.burp.host}:{cfg.burp.port}[/]")
        raise SystemExit(1)
    workdir = _prepare_workdir(cfg)

    for serial in _require_devices(cfg.device_serial):
        try:
            name = burp_mod.install_certificate(serial, cfg.burp.host, cfg.burp.port, workdir, force=force)
            console.print(f"[green]{serial}: certificate installed ({name}). Reboot the device to apply.[/]")
        except burp_mod.BurpError as exc:
            console.print(f"[yellow]{serial}: {escape(str(exc))}[/]")


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
    """Install/upgrade frida-server on the connected device(s)."""
    _require_internet()
    workdir = _prepare_workdir(cfg)
    for serial in _require_devices(cfg.device_serial):
        try:
            version = frida_tools.ensure_frida_server(serial, workdir, prefer_magisk=cfg.prefer_magisk, force=force)
            console.print(f"[green]{serial}: frida-server ready (version {version}).[/]")
        except frida_tools.FridaError as exc:
            console.print(f"[red]{serial}: {escape(str(exc))}[/]")


@cli.command("frida-check")
@click.pass_obj
def frida_check_cmd(cfg: Config):
    """Compare Frida versions across latest release, PC, and device(s)."""
    for serial in _require_devices(cfg.device_serial):
        info = frida_tools.check_version_mismatch(serial)
        console.print(f"{serial}: {info}")
        if not info["in_sync"]:
            console.print(
                f"[yellow]{serial}: versions differ; run 'pen-andro frida-server --force' "
                "or upgrade the PC package.[/]"
            )


@cli.command("apps")
@click.pass_obj
def apps_cmd(cfg: Config):
    """Install helper Android apps (ProxyToggle, ProxyDroid, ADB WiFi)."""
    _require_internet()
    workdir = _prepare_workdir(cfg)
    for serial in _require_devices(cfg.device_serial):
        for name, status in android_apps.install_all(serial, workdir).items():
            console.print(f"{serial}: {name}: {status}")


@cli.command("all")
@click.option("--force-frida", is_flag=True, help="Reinstall frida-server even if present")
@click.pass_obj
def all_cmd(cfg: Config, force_frida: bool):
    """Run the full setup: connectivity, root, PC tools, apps, Frida, and cert (per device)."""
    _require_internet()
    workdir = _prepare_workdir(cfg)

    pc_tools.install_missing()
    frida_tools.install_pc_tools()

    for serial in _require_devices(cfg.device_serial):
        for name, status in android_apps.install_all(serial, workdir).items():
            console.print(f"{serial}: {name}: {status}")

        try:
            version = frida_tools.ensure_frida_server(
                serial, workdir, prefer_magisk=cfg.prefer_magisk, force=force_frida
            )
            console.print(f"[green]{serial}: frida-server ready (version {version}).[/]")
        except frida_tools.FridaError as exc:
            console.print(f"[red]{serial}: {escape(str(exc))}[/]")

        if burp_mod.is_burp_running(cfg.burp.host, cfg.burp.port):
            try:
                name = burp_mod.install_certificate(serial, cfg.burp.host, cfg.burp.port, workdir)
                console.print(f"[green]{serial}: certificate installed ({name}).[/]")
            except burp_mod.BurpError as exc:
                console.print(f"[yellow]{serial}: {escape(str(exc))}[/]")
        else:
            console.print(f"[yellow]{serial}: skipping certificate install, Burp not reachable.[/]")

    console.print("[bold green]Setup complete. Reboot the device(s) to apply all changes.[/]")


def main():
    try:
        cli()
    except adb_mod.AdbError as exc:
        # Defense in depth: every known call site already catches AdbError and
        # exits cleanly, but a future command that forgets to should still
        # fail with a readable message instead of a raw traceback.
        console.print(f"[red]{escape(str(exc))}[/]")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
