"""CLI-level tests: mainly guarding the AdbError-handling fix.

Regression coverage for a real bug found while adding multi-device
fan-out: AdbError (raised by adb.resolve_device[s]() when zero, multiple,
or an unknown serial is involved) was never caught in cli.py, so it used
to propagate as a raw traceback instead of a clean error message — and its
text contains a Python list repr (e.g. "['a', 'b']"), which can break
Rich's markup parser if interpolated into a colored string unescaped.
"""
from click.testing import CliRunner

from pen_andro import adb
from pen_andro import cli as cli_mod


def test_doctor_reports_no_device_cleanly_instead_of_traceback(monkeypatch):
    monkeypatch.setattr(cli_mod.network, "has_internet", lambda: True)
    monkeypatch.setattr(cli_mod.burp_mod, "is_burp_running", lambda host, port: False)
    monkeypatch.setattr(adb, "list_devices", lambda: [])

    runner = CliRunner()
    result = runner.invoke(cli_mod.cli, ["doctor"])

    assert result.exit_code == 0  # doctor degrades gracefully, doesn't crash
    assert "No ADB device found" in result.output
    assert "Traceback" not in result.output


def test_cert_exits_cleanly_when_multiple_devices_and_no_serial_given(monkeypatch):
    monkeypatch.setattr(cli_mod.network, "has_internet", lambda: True)
    monkeypatch.setattr(cli_mod.burp_mod, "is_burp_running", lambda host, port: True)
    monkeypatch.setattr(
        adb, "list_devices", lambda: [adb.Device("a", "device"), adb.Device("b", "device")]
    )

    runner = CliRunner()
    result = runner.invoke(cli_mod.cli, ["cert"])

    assert result.exit_code == 1
    assert "Multiple devices connected" in result.output
    assert "Traceback" not in result.output
    # the bracketed serial list must render as plain text, not break markup
    assert "['a', 'b']" in result.output


def test_frida_server_fans_out_to_every_connected_device(monkeypatch):
    monkeypatch.setattr(cli_mod.network, "has_internet", lambda: True)
    monkeypatch.setattr(
        adb, "list_devices", lambda: [adb.Device("a", "device"), adb.Device("b", "device")]
    )
    monkeypatch.setattr(adb, "check_root", lambda serial: True)
    monkeypatch.setattr(
        cli_mod.frida_tools,
        "ensure_frida_server",
        lambda serial, workdir, prefer_magisk, force: f"1.0.0-{serial}",
    )

    runner = CliRunner()
    result = runner.invoke(cli_mod.cli, ["--device", "all", "frida-server"])

    assert result.exit_code == 0
    assert "a: frida-server ready (version 1.0.0-a)" in result.output
    assert "b: frida-server ready (version 1.0.0-b)" in result.output


def test_require_devices_skips_unrooted_devices_but_continues(monkeypatch):
    monkeypatch.setattr(
        adb, "list_devices", lambda: [adb.Device("a", "device"), adb.Device("b", "device")]
    )
    monkeypatch.setattr(adb, "check_root", lambda serial: serial == "b")

    ready = cli_mod._require_devices("all")
    assert ready == ["b"]


def test_require_devices_exits_when_none_rooted(monkeypatch):
    monkeypatch.setattr(adb, "list_devices", lambda: [adb.Device("a", "device")])
    monkeypatch.setattr(adb, "check_root", lambda serial: False)

    try:
        cli_mod._require_devices("all")
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert exc.code == 1
