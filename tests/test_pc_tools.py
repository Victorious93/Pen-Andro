from pen_andro import pc_tools


def test_missing_tools_reports_only_absent_binaries(monkeypatch):
    monkeypatch.setattr(pc_tools.shutil, "which", lambda tool: "/usr/bin/jadx" if tool == "jadx" else None)
    assert pc_tools.missing_tools() == ["apktool", "scrcpy"]


def test_install_missing_noop_when_nothing_missing(monkeypatch):
    monkeypatch.setattr(pc_tools, "missing_tools", lambda: [])
    assert pc_tools.install_missing() == []
