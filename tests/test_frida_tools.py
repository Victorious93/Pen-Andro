import pytest

from pen_andro import adb, frida_tools


def test_device_arch_maps_known_abis(monkeypatch):
    monkeypatch.setattr(adb, "get_cpu_abi", lambda serial: "arm64-v8a")
    assert frida_tools.device_arch("serial") == "arm64"


@pytest.mark.parametrize(
    "abi,expected",
    [
        ("x86_64", "x86_64"),
        ("x86", "x86"),
        ("armeabi-v7a", "arm"),
        ("armeabi", "arm"),
    ],
)
def test_device_arch_maps_all_known_abis(monkeypatch, abi, expected):
    monkeypatch.setattr(adb, "get_cpu_abi", lambda serial: abi)
    assert frida_tools.device_arch("serial") == expected


def test_device_arch_rejects_unknown_abi(monkeypatch):
    monkeypatch.setattr(adb, "get_cpu_abi", lambda serial: "mips")
    with pytest.raises(frida_tools.FridaError):
        frida_tools.device_arch("serial")


def test_check_version_mismatch_flags_out_of_sync(monkeypatch):
    monkeypatch.setattr(frida_tools, "latest_frida_version", lambda: "16.2.1")
    monkeypatch.setattr(frida_tools, "pc_frida_version", lambda: "16.1.0")
    monkeypatch.setattr(frida_tools, "android_frida_version", lambda serial: "16.0.0")
    info = frida_tools.check_version_mismatch("serial")
    assert info == {
        "latest": "16.2.1",
        "pc": "16.1.0",
        "android": "16.0.0",
        "in_sync": False,
    }


def test_check_version_mismatch_flags_in_sync(monkeypatch):
    monkeypatch.setattr(frida_tools, "latest_frida_version", lambda: "16.2.1")
    monkeypatch.setattr(frida_tools, "pc_frida_version", lambda: "16.2.1")
    monkeypatch.setattr(frida_tools, "android_frida_version", lambda serial: "16.2.1")
    assert frida_tools.check_version_mismatch("serial")["in_sync"] is True


def test_ensure_frida_server_skips_when_present_and_not_forced(monkeypatch):
    monkeypatch.setattr(frida_tools, "android_frida_version", lambda serial: "16.2.1")
    called = []
    monkeypatch.setattr(frida_tools, "is_magisk_available", lambda serial: called.append("magisk") or True)
    version = frida_tools.ensure_frida_server("serial", None, prefer_magisk=True, force=False)
    assert version == "16.2.1"
    assert called == []  # never checked for magisk, since we short-circuited


def test_ensure_frida_server_prefers_magisk_when_available(monkeypatch, tmp_path):
    monkeypatch.setattr(frida_tools, "android_frida_version", lambda serial: None)
    monkeypatch.setattr(frida_tools, "is_magisk_available", lambda serial: True)
    monkeypatch.setattr(frida_tools, "install_magisk_frida_module", lambda serial, workdir: "1.2.3")
    monkeypatch.setattr(
        frida_tools,
        "install_frida_server_manual",
        lambda serial, workdir, version=None: (_ for _ in ()).throw(AssertionError("should not be called")),
    )
    version = frida_tools.ensure_frida_server("serial", tmp_path, prefer_magisk=True)
    assert version == "1.2.3"


def test_ensure_frida_server_falls_back_to_manual_without_magisk(monkeypatch, tmp_path):
    monkeypatch.setattr(frida_tools, "android_frida_version", lambda serial: None)
    monkeypatch.setattr(frida_tools, "is_magisk_available", lambda serial: False)
    monkeypatch.setattr(frida_tools, "install_frida_server_manual", lambda serial, workdir, version=None: "9.9.9")
    version = frida_tools.ensure_frida_server("serial", tmp_path, prefer_magisk=True)
    assert version == "9.9.9"
