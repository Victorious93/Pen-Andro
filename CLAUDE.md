# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```console
pip install -e ".[dev]"                     # install package + dev deps (pytest, ruff, flask)
pytest                                       # run the full test suite (hermetic, no device/network)
pytest tests/test_frida_tools.py::test_device_arch_maps_known_abis   # run a single test
pytest --cov=pen_andro --cov-report=term-missing   # with coverage
PEN_ANDRO_RUN_DEVICE_TESTS=1 pytest -m device   # opt-in: needs a real rooted device connected
ruff check pen_andro tests                   # lint
pen-andro --help                             # CLI entry point (installed via pip -e .)
python -m pen_andro                          # equivalent, without relying on entry_points
pen-andro init                               # interactive config.yaml wizard
pen-andro --device all frida-server          # fan out a command across every connected device
pen-andro-gui                                # Tkinter GUI entry point
pen-andro-web                                # Flask web dashboard, 127.0.0.1:8765 by default (pip install -e ".[web]")
pip install -e ".[build]" && pyinstaller --onefile --name pen-andro --paths "$PWD" scripts/pyinstaller_entry.py  # standalone CLI binary
docker compose build && docker compose run --rm pen-andro doctor   # containerized PC-tools only
```

No device or network is required to run the default test suite — every
test monkeypatches the `adb`/`shell`/`requests` boundary rather than
touching a real device or the internet. The one exception is
`tests/test_device_integration.py` (marked `device`), gated behind
`PEN_ANDRO_RUN_DEVICE_TESTS=1` and skipped otherwise; see
`tests/conftest.py`.

## Architecture

Pen-Andro automates Android pentesting environment setup (Burp CA cert,
Frida server, helper apps, PC tools). It was rewritten from a single
~500-line Bash script (now `legacy/main.sh`, unmaintained) into a Python
package; see `PHASES.md` for the full rationale if you need the "why", not
just the "what".

**Layering is strict and one-directional**: every module that touches a
device does so exclusively through `pen_andro/adb.py`, which itself is the
only module that touches `pen_andro/shell.py`'s `run()` (a `subprocess`
wrapper that takes argument lists only — never `shell=True` — because a
Burp host:port or device serial can come from user input). When adding a
new capability, follow this pattern: put the logic in a new domain module
(like `frida_tools.py` or `burp.py`), have it depend on `adb.py` for device
I/O, and never shell out directly from `cli.py`/`menu.py`/`gui.py`.

**Four interfaces share one core.** `cli.py` (Click-based subcommands),
`menu.py` (the original numbered interactive menu, entered when `pen-andro`
runs with no subcommand), `gui.py` (Tkinter, runs each action in a
background thread and drains a `queue.Queue` into a log widget so the UI
doesn't block), and `webapp.py` (Flask, same background-worker idea but
polled over HTTP via `/api/log` instead of a Tkinter queue — see below) all
call the exact same functions in `adb.py`, `burp.py`, `frida_tools.py`,
`pc_tools.py`, and `android_apps.py`. Business logic should never live in
`cli.py`/`menu.py`/`gui.py`/`webapp.py` themselves — those files are wiring
only, so behavior stays consistent across all four entry points. New
functionality goes in a core module first, then gets wired into whichever
interfaces need it. `menu.py` and `gui.py` are deliberately single-device
only (they match the original tool's interactive UX); multi-device
fan-out (below) is CLI/web-only, since that's where scripting a fleet of
devices actually makes sense.

**Multi-device fan-out** (`adb.resolve_devices`, plural): `--device all`
runs a CLI command against every connected, rooted device, sequentially
(not concurrently — parallel adb/root operations against the same
`workdir` would race), skipping any device that fails the root check
rather than aborting the whole run. `adb.resolve_device` (singular, used
by `menu.py`/`gui.py`/`webapp.py`) is a thin wrapper around
`resolve_devices` that errors if it resolves to more than one device.
`cli.py`'s device-bound commands go through a shared `_require_devices()`
helper — don't reimplement device resolution per-command.

**`cli.py` catches `AdbError` and escapes interpolated text — don't
remove either.** `AdbError` messages (raised by `resolve_device[s]` for
"no device"/"multiple devices"/"unknown serial") contain a Python list
repr like `"['a', 'b']"`. If that text is interpolated into an f-string
passed to `rich.console.Console.print` without `rich.markup.escape()`,
the brackets can be misparsed as (invalid) Rich style tags. Every place
that prints an exception's `str()` inside a `[color]...[/]` span — in
`cli.py` and `menu.py` — wraps it in `escape()` for this reason; keep
doing that for any new one you add. `cli.py`'s `main()` also has an
`AdbError` catch-all as defense in depth, in case a future command forgets
its own.

**`webapp.py` is localhost-only by default, on purpose.** It grants the
same root/USB device control as the CLI/GUI, so `pen-andro-web` binds to
`127.0.0.1:8765` unless `--host` is explicitly overridden (which prints a
loud warning). It runs one action at a time via a single background
thread + lock (`/api/run/<action>` returns 409 if something's already
running) and polls `/api/log`, which HTML-escapes every line before
returning it — don't remove that escaping, log lines can contain error
text from device output. It's an optional install (`pip install -e
".[web]"`) so Flask isn't a hard dependency for CLI-only users.

**Frida install has a decision tree** (`frida_tools.ensure_frida_server`):
if a frida-server already responds on-device and `force` isn't set, it's
left alone. Otherwise, if Magisk is present and `prefer_magisk` is true
(config default), a Magisk module is flashed (`install_magisk_frida_module`)
— this is the only path that survives a reboot. Without Magisk, a
frida-server binary matching the device's CPU ABI is downloaded and pushed
to `/system/xbin` (`install_frida_server_manual`), which does not survive a
reboot and must be re-run each time. `ARCH_MAP` in `frida_tools.py` is the
single source of truth for ABI → Frida release-asset-suffix mapping.

**`android_apps.py` mixes two install sources deliberately**: ProxyDroid
and ADB WiFi install from APKs already vendored in `assets/` (avoids
depending on a third-party mirror repo that original script pulled from),
while ProxyToggle has no local copy and is fetched from its actual upstream
release (a zip containing `proxy-toggle.apk`). `AndroidApp.source_type`
(`"local"` vs `"zip"`) selects between these in `_resolve_apk` — don't add
a third source type without a reason; two through-lines already cover
every app it currently manages.

**Config precedence** (`config.py`): YAML file (`config.yaml`, or
`~/.config/pen-andro/config.yaml`) → environment variables
(`PEN_ANDRO_BURP_HOST`, `PEN_ANDRO_BURP_PORT`, `PEN_ANDRO_DEVICE`) → CLI
flags (`--device`, applied in `cli.py` after `load_config()`). Env vars are
read at config-load time, so tests that assert defaults must clear them
first (see `tests/test_config.py::_clear_env`).

**Multi-device handling** (`adb.py`): `resolve_device()` is the single
choke point every command/menu action/GUI button calls before doing
anything else. It raises `AdbError` if zero devices are online, if a
requested serial isn't among them, or if more than one device is online and
no serial was given — callers should let `AdbError` propagate to the
interface layer rather than re-implementing device-selection logic.

The Docker image (`Dockerfile`, Kali-rolling based) only provides the
PC-tools half of the workflow; on-device steps (root cert install, Magisk
flashing) require the host's real Magisk/root setup and can't happen
inside the container — this is a hard constraint, not a TODO.

**PyInstaller builds need `--paths`.** `scripts/pyinstaller_entry.py` is
the build entry point (PyInstaller needs a script file, not a `-m` module
target). Building from an editable install (`pip install -e .`) without
`--paths <source-tree>` fails with `ModuleNotFoundError: No module named
'pen_andro'` — PyInstaller's static analysis doesn't follow the import
hooks modern editable installs use. `.github/workflows/build.yml` and the
command above already pass it; if you're packaging via a different route,
keep it. Only the CLI is packaged this way — the Tkinter GUI and Flask web
dashboard have their own bundling concerns and aren't included in this
binary.
