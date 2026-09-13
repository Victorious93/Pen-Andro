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

## Explicitly out of scope

Raised during planning and deliberately not built, so nobody wonders why
they're missing:
- **iOS support** — this tool's entire model (root/ADB/Magisk/Frida-on-Android)
  doesn't transfer; it would be a separate project, not a feature flag here.
- **Cloud/remote device farms** — no device-farm integration was requested
  and it changes the trust/network model significantly; left for a future,
  explicitly-scoped effort.
- **Web dashboard** — the Tkinter GUI covers the "not a terminal menu" need
  without adding a server/browser attack surface for a tool that already
  requires local root/USB access.
