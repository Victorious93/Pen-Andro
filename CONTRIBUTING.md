# Contributing to Pen-Andro

## Setup

```console
git clone https://github.com/raoshaab/Pen-Andro.git
cd Pen-Andro
pip install -e ".[dev]"
```

`dev` pulls in `pytest`, `ruff`, and `flask` (so the web dashboard's tests
run without a separate install). PyInstaller packaging needs its own extra:
`pip install -e ".[build]"`.

## Running checks

```console
ruff check pen_andro tests
pytest                                          # unit tests — mocked, no device/network needed
PEN_ANDRO_RUN_DEVICE_TESTS=1 pytest -m device   # opt-in, needs a real rooted device connected
```

The default `pytest` run is fully hermetic: every test mocks the
`adb`/`shell`/`requests` boundary. The `device` marker in
`tests/test_device_integration.py` is the only exception — it's opt-in and
skipped unless you set `PEN_ANDRO_RUN_DEVICE_TESTS=1` with a real device
connected, and it's read-only (checks root/arch/connectivity, never
installs anything) so it's safe to run repeatedly.

## Architecture

Read `CLAUDE.md` before making changes — it documents the module layering
(`adb.py` is the only module that talks to a device; every domain module
depends on it, never the other way around) and where new functionality
belongs. `PHASES.md` records why the project is shaped this way, including
what was deliberately left out and why, if you need the history rather
than just the current state.

## Before opening a PR

- New behavior goes in a core module first (`adb.py`, `burp.py`,
  `frida_tools.py`, `pc_tools.py`, `android_apps.py`, `config.py`), then
  gets wired into whichever of `cli.py` / `menu.py` / `gui.py` / `webapp.py`
  need it. Don't duplicate logic across interfaces — they exist to be thin
  wiring around the same core.
- `ruff check` and `pytest` must pass before you push.
- If you touch `frida_tools.py`'s `ARCH_MAP` or its version-resolution
  logic, add a unit test with a mocked ABI/version — don't rely on manual
  device testing alone, since CI can't run those.
- If you touch device I/O in `adb.py`, mock `adb.run`/`adb.shell` in tests
  rather than requiring a real device; the opt-in `device` marker is for
  end-to-end confidence, not for covering new logic branches.
