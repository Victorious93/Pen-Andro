from pen_andro import adb, android_apps
from pen_andro.shell import CommandResult


def test_is_installed_true(monkeypatch):
    monkeypatch.setattr(
        adb,
        "shell",
        lambda serial, cmd, **kw: CommandResult(0, "package:org.proxydroid\npackage:com.example\n", ""),
    )
    assert android_apps.is_installed("serial", "org.proxydroid") is True


def test_is_installed_false(monkeypatch):
    monkeypatch.setattr(
        adb, "shell", lambda serial, cmd, **kw: CommandResult(0, "package:com.example\n", "")
    )
    assert android_apps.is_installed("serial", "org.proxydroid") is False


def test_install_app_skips_when_already_installed(monkeypatch, tmp_path):
    monkeypatch.setattr(android_apps, "is_installed", lambda serial, package: True)
    app = android_apps.APPS[0]
    result = android_apps.install_app("serial", app, tmp_path)
    assert result is False


def test_install_all_reports_failure_without_raising(monkeypatch, tmp_path):
    monkeypatch.setattr(android_apps, "is_installed", lambda serial, package: False)

    def boom(serial, app, workdir):
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(android_apps, "install_app", boom)
    results = android_apps.install_all("serial", tmp_path)
    assert all(status.startswith("failed:") for status in results.values())
    assert len(results) == len(android_apps.APPS)
