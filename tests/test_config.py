from pen_andro.config import load_config


def _clear_env(monkeypatch):
    for var in ("PEN_ANDRO_BURP_HOST", "PEN_ANDRO_BURP_PORT", "PEN_ANDRO_DEVICE"):
        monkeypatch.delenv(var, raising=False)


def test_load_config_defaults_when_no_file(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    cfg = load_config(str(tmp_path / "missing.yaml"))
    assert cfg.burp.host == "127.0.0.1"
    assert cfg.burp.port == 8080
    assert cfg.device_serial is None
    assert cfg.prefer_magisk is True


def test_load_config_reads_yaml(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "burp:\n  host: 10.0.0.5\n  port: 9001\ndevice_serial: emulator-5554\nprefer_magisk: false\n"
    )
    cfg = load_config(str(config_file))
    assert cfg.burp.host == "10.0.0.5"
    assert cfg.burp.port == 9001
    assert cfg.device_serial == "emulator-5554"
    assert cfg.prefer_magisk is False


def test_env_overrides_yaml(tmp_path, monkeypatch):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("burp:\n  host: 10.0.0.5\n  port: 9001\n")
    monkeypatch.setenv("PEN_ANDRO_BURP_HOST", "192.168.1.50")
    monkeypatch.setenv("PEN_ANDRO_DEVICE", "emulator-5554")
    cfg = load_config(str(config_file))
    assert cfg.burp.host == "192.168.1.50"
    assert cfg.burp.port == 9001  # untouched by env
    assert cfg.device_serial == "emulator-5554"
