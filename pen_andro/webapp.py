"""Localhost-only web dashboard for Pen-Andro.

Optional install: `pip install -e ".[web]"`. Binds to 127.0.0.1 by default
on purpose — this tool grants root/USB control over an Android device, so
exposing it beyond localhost is opt-in and loudly warned about, not the
default, the way the CLI/menu/GUI already are (local-only by construction).

Actions run in a single background worker thread (one job at a time, since
concurrent adb/root operations against the same workdir would race); the
page polls /api/log to show progress, the same pattern gui.py uses with a
Tkinter queue instead of HTTP polling.
"""
from __future__ import annotations

import argparse
import threading
from html import escape

from . import adb as adb_mod
from . import android_apps, frida_tools, network, pc_tools
from . import burp as burp_mod
from .config import load_config

try:
    from flask import Flask, jsonify
except ImportError as exc:  # pragma: no cover - exercised only when flask isn't installed
    raise SystemExit(
        "The web dashboard needs Flask. Install it with: pip install -e '.[web]'"
    ) from exc

app = Flask(__name__)

_lock = threading.Lock()
_log_lines: list[str] = []
_running = False


def _log(message: str) -> None:
    _log_lines.append(message)


def _device_serial(cfg) -> str:
    device = adb_mod.resolve_device(cfg.device_serial)
    _log(f"adb connected: {device.serial}")
    if not adb_mod.check_root(device.serial):
        raise RuntimeError("Root access denied; grant root to adb and retry.")
    return device.serial


def _run_action(name: str) -> None:
    global _running
    cfg = load_config()
    cfg.workdir.mkdir(parents=True, exist_ok=True)
    try:
        if name == "all":
            if not network.has_internet():
                _log("No internet connectivity.")
                return
            serial = _device_serial(cfg)
            pc_tools.install_missing()
            frida_tools.install_pc_tools()
            _log(str(android_apps.install_all(serial, cfg.workdir)))
            version = frida_tools.ensure_frida_server(serial, cfg.workdir, prefer_magisk=cfg.prefer_magisk)
            _log(f"frida-server ready: {version}")
            if burp_mod.is_burp_running(cfg.burp.host, cfg.burp.port):
                try:
                    cert_name = burp_mod.install_certificate(serial, cfg.burp.host, cfg.burp.port, cfg.workdir)
                    _log(f"Certificate installed: {cert_name}")
                except burp_mod.BurpError as exc:
                    _log(str(exc))
            _log("Setup complete. Reboot the device to apply changes.")
        elif name == "cert":
            serial = _device_serial(cfg)
            if not burp_mod.is_burp_running(cfg.burp.host, cfg.burp.port):
                _log(f"Burp not reachable at {cfg.burp.host}:{cfg.burp.port}")
                return
            cert_name = burp_mod.install_certificate(
                serial, cfg.burp.host, cfg.burp.port, cfg.workdir, force=True
            )
            _log(f"Installed {cert_name}. Reboot to apply.")
        elif name == "pc-tools":
            missing = pc_tools.install_missing()
            _log(f"Still missing: {missing}" if missing else "jadx/apktool/scrcpy ready.")
            frida_tools.install_pc_tools()
            _log("frida & objection ready.")
        elif name == "frida-server":
            serial = _device_serial(cfg)
            version = frida_tools.ensure_frida_server(serial, cfg.workdir, prefer_magisk=cfg.prefer_magisk)
            _log(f"frida-server ready: {version}")
        elif name == "frida-check":
            serial = _device_serial(cfg)
            _log(str(frida_tools.check_version_mismatch(serial)))
        elif name == "apps":
            serial = _device_serial(cfg)
            _log(str(android_apps.install_all(serial, cfg.workdir)))
        else:
            _log(f"Unknown action: {name}")
    except Exception as exc:
        _log(f"ERROR: {exc}")
    finally:
        with _lock:
            _running = False


_ACTIONS = ("all", "cert", "pc-tools", "frida-server", "frida-check", "apps")

_PAGE = """<!doctype html>
<title>Pen-Andro</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem; background: #111; color: #eee; }
  button { margin: 0 0.5rem 0.5rem 0; padding: 0.5rem 1rem; cursor: pointer; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  #log { background: #000; color: #0f0; padding: 1rem; height: 60vh; overflow-y: auto;
         white-space: pre-wrap; font-family: monospace; border-radius: 4px; }
</style>
<h1>Pen-Andro</h1>
<p>Local dashboard — actions run against the ADB device selected by config.yaml / PEN_ANDRO_DEVICE.</p>
<div id="buttons"></div>
<div id="log"></div>
<script>
const actions = %(actions)s;
const buttonsEl = document.getElementById("buttons");
actions.forEach(name => {
  const btn = document.createElement("button");
  btn.textContent = name;
  btn.onclick = () => run(name);
  buttonsEl.appendChild(btn);
});

async function run(name) {
  const res = await fetch(`/api/run/${name}`, { method: "POST" });
  if (res.status === 409) {
    alert("A task is already running.");
  }
}

async function poll() {
  const res = await fetch("/api/log");
  const data = await res.json();
  const logEl = document.getElementById("log");
  logEl.textContent = data.lines.join("\\n");
  logEl.scrollTop = logEl.scrollHeight;
  document.querySelectorAll("button").forEach(b => b.disabled = data.running);
}
setInterval(poll, 1000);
poll();
</script>
"""


@app.route("/")
def index():
    import json

    return _PAGE % {"actions": json.dumps(_ACTIONS)}


@app.route("/api/run/<action>", methods=["POST"])
def run_action(action: str):
    global _running
    if action not in _ACTIONS:
        return jsonify({"error": "unknown action"}), 404
    with _lock:
        if _running:
            return jsonify({"error": "a task is already running"}), 409
        _running = True
        _log_lines.clear()
        _log_lines.append(f"$ {action}")
    threading.Thread(target=_run_action, args=(action,), daemon=True).start()
    return jsonify({"started": action})


@app.route("/api/log")
def get_log():
    with _lock:
        return jsonify({"lines": [escape(line) for line in _log_lines], "running": _running})


def main() -> None:
    parser = argparse.ArgumentParser(description="Pen-Andro web dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(
            f"WARNING: binding to {args.host} exposes root/USB control of your Android device "
            "to anyone who can reach this port. Only do this on a trusted network."
        )

    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
