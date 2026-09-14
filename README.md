# Pen-Andro

[![CI](https://github.com/raoshaab/Pen-Andro/actions/workflows/ci.yml/badge.svg)](https://github.com/raoshaab/Pen-Andro/actions/workflows/ci.yml)
[![HitCount](https://hits.dwyl.com/raoshaab/raoshaab/Pen-Andro.svg?style=flat-square)](http://hits.dwyl.com/raoshaab/raoshaab/Pen-Andro)

![](./assets/animation.gif)

## 💥 Introduction

Pen-Andro automates the repetitive setup work for Android penetration
testing: installing the Burp Suite CA certificate onto a rooted device,
installing Frida server (matched to the device's CPU and, when Magisk is
present, persisted across reboots), and installing helper apps
(ProxyToggle, ProxyDroid, ADB WiFi) and PC-side tools (JADX, apktool,
scrcpy, Frida, objection).

It ships as a Python package with a CLI, an interactive terminal menu, an
optional Tkinter GUI, and an optional local web dashboard — the original
Bash script is kept under `legacy/` for reference but is no longer
maintained.

## 🛠️ Installation

```console
git clone https://github.com/raoshaab/Pen-Andro.git
cd Pen-Andro
pip install -e .
```

> **Security note:** earlier versions of this README recommended
> `curl -sL <shortlink> | sudo bash` — running a script fetched from a URL
> shortener directly as root, with no way to review it first or verify its
> integrity. That pattern is a real supply-chain risk and has been dropped.
> Clone the repo, read `pen_andro/`, then install it.

Optional extras:

```console
pip install -e ".[dev]"     # pytest, ruff, flask — for running tests/lint
pip install -e ".[web]"     # flask only — for the web dashboard (pen-andro-web)
pip install -e ".[build]"   # pyinstaller only — for packaging a standalone binary
```

The GUI (`pen-andro-gui`) uses Tkinter, which ships with most Python
installs; on some minimal Linux distros you may need `apt install
python3-tk` first.

### Standalone binary

```console
pip install -e ".[build]"
pyinstaller --onefile --name pen-andro --paths "$PWD" scripts/pyinstaller_entry.py
./dist/pen-andro --help
```

`--paths` is required — PyInstaller's static analysis doesn't follow the
import hooks a `pip install -e .` editable install uses, so without it the
build fails with `ModuleNotFoundError: No module named 'pen_andro'`.
Packages the CLI only (not the GUI or web dashboard). A GitHub Actions job
(`.github/workflows/build.yml`) builds this automatically on `v*` tags.

### Docker (PC-tools only)

```console
docker compose build
docker compose run --rm pen-andro doctor
```

This container provides jadx/apktool/scrcpy/frida/objection/adb, **not**
the on-device Magisk workflow — see the comment at the top of `Dockerfile`
for what does and doesn't work from inside a container.

## Preconditions

* Burp Suite's proxy running (default `127.0.0.1:8080`; configurable, see below)
* A rooted Android device or emulator connected via `adb`, with root access
  granted to `adb` from the on-device superuser manager
* [Magisk](https://github.com/topjohnwu/Magisk) installed (recommended —
  lets Pen-Andro install Frida as a module that survives reboots instead of
  pushing a binary that doesn't)
  1. For an Android Virtual Device: https://github.com/newbit1/rootAVD
  2. For Genymotion: https://support.genymotion.com/hc/en-us/articles/360011385178

## Configuration

Copy `config.example.yaml` to `config.yaml` and edit, or override any value
with an environment variable:

```yaml
burp:
  host: 127.0.0.1
  port: 8080
device_serial: null      # set this (or use --device) when multiple devices are connected
prefer_magisk: true
workdir: /tmp/pen_andro
pinned_frida_version: null
```

| Environment variable      | Overrides           |
|----------------------------|----------------------|
| `PEN_ANDRO_BURP_HOST`      | `burp.host`          |
| `PEN_ANDRO_BURP_PORT`      | `burp.port`          |
| `PEN_ANDRO_DEVICE`         | `device_serial`      |

## 🛠️ Usage

Run with no arguments for the classic interactive menu:

```console
pen-andro
```

```
1. All
2. Move Burp Suite certificate to the device
3. PC tools (jadx, apktool, scrcpy, frida, objection)
4. Android Frida server
5. Check/fix Frida version mismatch
6. Android apps (ProxyToggle, ProxyDroid, ADB WiFi)
0. Exit
```

Or drive it as a normal CLI (useful in scripts/CI):

```console
pen-andro init                    # interactive config.yaml wizard
pen-andro doctor                  # check internet, Burp, adb, root (per device)
pen-andro cert [--force]          # install the Burp CA certificate
pen-andro pc-tools                # install jadx, apktool, scrcpy, frida, objection
pen-andro frida-server [--force]  # install/upgrade frida-server on the device
pen-andro frida-check             # compare latest/PC/device Frida versions
pen-andro apps                    # install ProxyToggle, ProxyDroid, ADB WiFi
pen-andro all [--force-frida]     # run everything above
```

Every device-bound command accepts `--device <serial>` and `--config
<path>`. Pass `--device all` to run against every connected, rooted device
in one go (sequentially, so downloads to the shared workdir don't race);
devices that fail the root check are skipped with a warning rather than
aborting the whole run:

```console
pen-andro --device all frida-server
```

Or launch the GUI:

```console
pen-andro-gui
```

Or the web dashboard (binds to `127.0.0.1:8765` by default — it grants the
same root/USB device control as the CLI, so treat `--host` like you would
any other local-admin tool):

```console
pip install -e ".[web]"
pen-andro-web
```

## Screenshots

<img src="./assets/screen.gif" />

## 🛠️ Features

### Android Apps
* Proxy droid

 <img src="./assets/proxy_droid.png" width="64" align="center"/>

* ADB wifi

<img src="./assets/adb_wifi.png" width="64" align="center"/>

* Proxy Toggle

<img src="./assets/proxy_toggle.png" width="64" align="center"/>

### PC Tools
* Frida, objection & Frida server for Android

<img src="./assets/frida.svg" width="81" align="center" />

* JADX GUI

<img src="./assets/jadx-logo.png" width="64" align="center" />

* scrcpy

<img src="./assets/scrcpy.svg" alt="scrcpy" align="center" width="60" />

* Burp Suite certificate install

<img src="./assets/burpsuite-logo.svg" alt="scrcpy" align="center" width="64" />

## Development

```console
pip install -e ".[dev]"
ruff check pen_andro tests
pytest --cov=pen_andro
PEN_ANDRO_RUN_DEVICE_TESTS=1 pytest -m device   # opt-in, needs a real rooted device
```

See `CONTRIBUTING.md` for the full dev workflow, `PHASES.md` for the
architecture rationale (including what was deliberately left out and why),
and `CLAUDE.md` for guidance aimed at AI coding agents working in this
repo.

## FAQs

* **Burp error** — check the Proxy tab of Burp Suite and confirm the
  listener matches your `config.yaml` (`127.0.0.1:8080` by default).
* **Root access error** — confirm your device is rooted and that `adb` has
  been granted root by the on-device superuser manager.
* **Traffic not intercepting** — reboot the device after certificate
  installation.
* **"Multiple devices connected"** — pass `--device <serial>` or `--device
  all` (or set `device_serial` in `config.yaml`); run `adb devices` to see
  serials, or `adb kill-server` to clear stale offline entries.

## Not supported

iOS and cloud/remote device farms are deliberately not implemented — see
"Round 2" in `PHASES.md` for why. Both would need a fundamentally
different device-communication layer than the ADB/root/Magisk model this
tool is built around; adding either here would mean a parallel,
undertested codebase rather than a feature of this one.

## Credits

1. skylot — https://github.com/skylot/jadx
2. frida — https://github.com/frida/frida
3. Madeye — https://github.com/madeye/proxydroid
4. Sujan Poudel — https://github.com/psuzn/ADB-WiFi
5. Voicu Klein, Fidel Montesino — https://github.com/theappbusiness/android-proxy-toggle
6. Genymobile — https://github.com/Genymobile/scrcpy
7. ViRb3 — https://github.com/ViRb3/magisk-frida
8. NVISOsecurity — https://github.com/NVISOsecurity/MagiskTrustUserCerts

## License

GPL-3.0-or-later — see `LICENSE`.
