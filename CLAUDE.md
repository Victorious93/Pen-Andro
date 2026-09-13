# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```console
pip install -e ".[dev]"                     # install package + dev deps (pytest, ruff)
pytest                                       # run the full test suite
pytest tests/test_frida_tools.py::test_device_arch_maps_known_abis   # run a single test
pytest --cov=pen_andro --cov-report=term-missing   # with coverage
ruff check pen_andro tests                   # lint
pen-andro --help                             # CLI entry point (installed via pip -e .)
python -m pen_andro                          # equivalent, without relying on entry_points
pen-andro-gui                                # Tkinter GUI entry point
docker compose build && docker compose run --rm pen-andro doctor   # containerized PC-tools only
```

No device or network is required to run the test suite — every test
monkeypatches the `adb`/`shell`/`requests` boundary rather than touching a
real device or the internet.

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

**Three interfaces share one core.** `cli.py` (Click-based subcommands),
`menu.py` (the original numbered interactive menu, entered when `pen-andro`
runs with no subcommand), and `gui.py` (Tkinter, runs each action in a
background thread and drains a `queue.Queue` into a log widget so the UI
doesn't block) all call the exact same functions in `adb.py`, `burp.py`,
`frida_tools.py`, `pc_tools.py`, and `android_apps.py`. Business logic
should never live in `cli.py`/`menu.py`/`gui.py` themselves — those files
are wiring only, so behavior stays consistent across all three entry
points. New functionality goes in a core module first, then gets wired
into whichever interfaces need it.

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
