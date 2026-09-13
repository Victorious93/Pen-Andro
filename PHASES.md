# Pen-Andro Modernization — Build Guide

This document tracks the rewrite of Pen-Andro from a single monolithic Bash
script (`main.sh`) into a maintainable Python package, and records why each
phase exists so future contributors (human or Claude) understand the
architecture instead of re-deriving it.

## Why rewrite

The original `main.sh`:
- Is a ~500-line Bash script with no tests, no modularity, and inconsistent
  error handling (some failures `exit`, some silently continue).
- Downloads and executes third-party APKs/modules from several external
  GitHub repos with no version pinning or checksum verification.
- Hardcodes `127.0.0.1:8080` for Burp and assumes exactly one ADB device.
- Has no automated verification — every change was tested by hand.
- The README's primary install path (`curl -sL <shortlink> | sudo bash`) runs
  unreviewed code as root with no integrity check — a real supply-chain risk.

The rewrite keeps every capability of the original script but makes it
testable, configurable, multi-device aware, and safer to install.

## Phases

### Phase 1 — Scaffolding
`pyproject.toml`, `requirements.txt`, `requirements-dev.txt`,
`config.example.yaml`, and the `pen_andro/` package skeleton
(`__init__.py`, `__main__.py`). Establishes packaging so the tool installs
via `pip install -e .` and exposes `pen-andro` / `pen-andro-gui` entry
points instead of a downloaded shell script.

### Phase 2 — Core modules (`pen_andro/`)
Pure-logic modules with no interactive prompts, each independently testable:
- `shell.py` — subprocess wrapper (list-args only, never `shell=True`),
  returns a `CommandResult` instead of relying on `$?` string comparisons.
- `adb.py` — device discovery, multi-device resolution, root check,
  `adb shell` helper.
- `network.py` — connectivity check.
- `burp.py` — Burp proxy detection + CA certificate install.
- `frida_tools.py` — CPU ABI → Frida arch mapping, latest-version lookup,
  manual frida-server install, Magisk module install, version-mismatch
  check.
- `pc_tools.py` — jadx/apktool/scrcpy install via the host package manager.
- `android_apps.py` — ProxyToggle/ProxyDroid/ADB WiFi install, preferring
  the APKs already vendored under `assets/` over re-downloading from a
  third-party mirror.
- `config.py` — YAML config file + environment variable overrides
  (`PEN_ANDRO_*`), replacing hardcoded IPs/ports.

### Phase 3 — Interfaces
- `cli.py` — `click`-based CLI (`pen-andro doctor|cert|pc-tools|frida-server
  |frida-check|apps|all`) for scripting/CI use.
- `menu.py` — the original numbered interactive menu, rebuilt on top of the
  Phase 2 modules instead of duplicating logic.
- `gui.py` — a minimal Tkinter GUI (stdlib only, no extra dependency) for
  users who prefer clicking buttons over a terminal menu.

### Phase 4 — Tests
`pytest` unit tests for the deterministic parts of Phase 2 (device parsing,
ABI→arch mapping, config precedence, package-installed detection) using
monkeypatched subprocess calls — no real device or network required.

### Phase 5 — Docker + CI
- `Dockerfile` (Kali-rolling base, matching the original script's assumption
  that `jadx`/`apktool`/`scrcpy` are apt-installable) for the **PC-tools
  half only** — documented clearly, since USB device access from a
  container needs passthrough and on-device Magisk work can't happen in a
  container at all.
- `.github/workflows/ci.yml` — lint (`ruff`) + `pytest` on every push/PR.

### Phase 6 — Docs
- `README.md` rewritten around the new install/usage flow, with an explicit
  security note replacing the old curl-pipe-to-root-shell instructions.
- `legacy/main.sh` — the original script, kept for reference and marked
  deprecated rather than deleted.
- `CLAUDE.md` — architecture notes for future Claude Code sessions.

### Phase 7 — Validation
`pip install -e ".[dev]"`, `ruff check`, `pytest`, and a CLI smoke test
(`python -m pen_andro --help`) to confirm the package actually installs and
runs before calling the rewrite done.

## Round 2 — requested as "everything", scoped down by two items

After the Phase 1–7 rewrite merged, a follow-up request asked for
literally everything on the original candidate list, including the two
items Phase 1–7 had declined. Declining stood for one of them; the other
was reclassified as buildable once scoped narrowly:

- **Web dashboard — built.** `webapp.py` is a small Flask app reusing the
  exact same core-module functions as `cli.py`/`menu.py`/`gui.py`, binding
  to `127.0.0.1` by default with a loud warning if you override `--host`
  to anything else. The original objection ("adds a server/browser attack
  surface for a tool that needs local root/USB access") is addressed by
  making that surface localhost-only by construction, not by refusing to
  build it.
- **iOS support — still declined**, same reasoning as before: it isn't a
  feature of this codebase, it's a different tool (usbmuxd/SSH instead of
  ADB, a jailbreak-tool ecosystem instead of Magisk, a different cert
  install mechanism). Building it here would mean either an untested
  parallel codebase or a stub claiming support that doesn't exist.
- **Cloud/remote device farms — still declined**: no provider was named
  (AWS Device Farm, Firebase Test Lab, Genymotion Cloud, Corellium all have
  different APIs) and none are configured in this environment, so anything
  built here would be unvalidatable against a real account.

### Phase 8 — Multi-device fan-out
`adb.resolve_devices()` (plural) added alongside the existing
`resolve_device()`: `--device all` now runs a command against every
connected, rooted device sequentially (not concurrently, to avoid workdir
races), skipping any device that fails the root check rather than aborting
the whole run. `cli.py`'s `cert`/`frida-server`/`frida-check`/`apps`/`all`
commands were rewritten around a shared `_require_devices()` helper.
`menu.py`/`gui.py` stay single-device — fan-out is a scripting/CI need, not
an interactive-menu one.

Fixed a real bug found while doing this: `AdbError` was never caught
anywhere in `cli.py`, so "no device" or "multiple devices" used to
propagate as a raw Python traceback instead of a clean message — and its
text embeds a Python list repr (`"['a', 'b']"`), which can break Rich's
markup parser if interpolated into a colored string unescaped. Both are
fixed (`_require_devices` catches `AdbError`, `rich.markup.escape()` wraps
interpolated exception/list text) and covered by `tests/test_cli.py`.

### Phase 9 — Config wizard
`pen-andro init` prompts for Burp host/port, detects connected devices to
suggest a `device_serial` default, and writes `config.yaml` — replacing
hand-editing `config.example.yaml`.

### Phase 10 — Web dashboard
`pen_andro/webapp.py` (Flask, `pip install -e ".[web]"`). One background
worker thread at a time (concurrent adb/root operations against the same
workdir would race, same reasoning as fan-out being sequential); the page
polls `/api/log`, mirroring the queue-draining pattern `gui.py` already
uses for Tkinter. Log output is HTML-escaped before being sent to the
browser.

### Phase 11 — PyInstaller packaging
`scripts/pyinstaller_entry.py` + `.github/workflows/build.yml`, triggered
on `v*` tags or manually. This was actually built and run during
development, not just written and assumed to work: the first attempt
failed (`ModuleNotFoundError: No module named 'pen_andro'`) because
PyInstaller's static analysis doesn't follow the import hooks modern
`pip install -e .` editable installs use — fixed with an explicit
`--paths` flag pointing at the source tree, verified by actually running
the built binary's `--help`. Packages the CLI only; the Tkinter GUI and
Flask web dashboard aren't bundled (different packaging story for each,
not worth the added CI complexity for this round).

### Phase 12 — Device-integration test scaffolding
`tests/conftest.py`'s `real_device_serial` fixture and
`tests/test_device_integration.py`, gated behind
`PEN_ANDRO_RUN_DEVICE_TESTS=1` and a real connected device — skipped by
default so `pytest` stays hermetic. Deliberately read-only (root/arch/
connectivity checks only, no installs) so it's safe to run repeatedly
against a real test device.

### Phase 13 — CONTRIBUTING.md
Dev setup, check commands, and a pointer to `CLAUDE.md`/`PHASES.md` for
anyone opening a PR.
