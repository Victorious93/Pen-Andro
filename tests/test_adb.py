import pytest

from pen_andro import adb
from pen_andro.shell import CommandResult


def test_list_devices_parses_multiple_lines(monkeypatch):
    output = "List of devices attached\nemulator-5554\tdevice\n1234ABCD\toffline\n\n"
    monkeypatch.setattr(adb, "run", lambda cmd, **kw: CommandResult(0, output, ""))
    devices = adb.list_devices()
    assert devices == [
        adb.Device("emulator-5554", "device"),
        adb.Device("1234ABCD", "offline"),
    ]


def test_resolve_device_picks_single_online_device(monkeypatch):
    monkeypatch.setattr(
        adb,
        "list_devices",
        lambda: [adb.Device("emulator-5554", "device"), adb.Device("dead", "offline")],
    )
    device = adb.resolve_device()
    assert device.serial == "emulator-5554"


def test_resolve_device_picks_requested_serial(monkeypatch):
    monkeypatch.setattr(
        adb,
        "list_devices",
        lambda: [adb.Device("a", "device"), adb.Device("b", "device")],
    )
    device = adb.resolve_device("b")
    assert device.serial == "b"


def test_resolve_device_rejects_unknown_serial(monkeypatch):
    monkeypatch.setattr(adb, "list_devices", lambda: [adb.Device("a", "device")])
    with pytest.raises(adb.AdbError):
        adb.resolve_device("nope")


def test_resolve_device_requires_serial_when_multiple(monkeypatch):
    monkeypatch.setattr(
        adb,
        "list_devices",
        lambda: [adb.Device("a", "device"), adb.Device("b", "device")],
    )
    with pytest.raises(adb.AdbError):
        adb.resolve_device()


def test_resolve_device_raises_when_none_connected(monkeypatch):
    monkeypatch.setattr(adb, "list_devices", lambda: [])
    with pytest.raises(adb.AdbError):
        adb.resolve_device()


def test_check_root_true_when_su_succeeds(monkeypatch):
    monkeypatch.setattr(adb, "shell", lambda serial, cmd, **kw: CommandResult(0, "ok\n", ""))
    assert adb.check_root("serial") is True


def test_check_root_false_when_su_denied(monkeypatch):
    monkeypatch.setattr(
        adb, "shell", lambda serial, cmd, **kw: CommandResult(1, "", "Permission denied")
    )
    assert adb.check_root("serial") is False
