"""Tests for the Flask web dashboard, run against its test client (no real
server binds a port during tests)."""
import pytest

pytest.importorskip("flask")

from pen_andro import adb, webapp  # noqa: E402  (import after importorskip)


@pytest.fixture
def client():
    webapp.app.config["TESTING"] = True
    with webapp.app.test_client() as client:
        yield client
    with webapp._lock:
        webapp._log_lines.clear()
        webapp._running = False


def test_index_lists_every_action(client):
    response = client.get("/")
    assert response.status_code == 200
    for action in webapp._ACTIONS:
        assert action in response.get_data(as_text=True)


def test_run_unknown_action_is_rejected(client):
    response = client.post("/api/run/not-a-real-action")
    assert response.status_code == 404


def test_run_rejects_concurrent_jobs(client):
    with webapp._lock:
        webapp._running = True
    response = client.post("/api/run/pc-tools")
    assert response.status_code == 409


def test_run_starts_a_job_and_log_reflects_it(client, monkeypatch):
    monkeypatch.setattr(webapp.pc_tools, "install_missing", lambda: [])
    monkeypatch.setattr(webapp.frida_tools, "install_pc_tools", lambda: True)

    response = client.post("/api/run/pc-tools")
    assert response.status_code == 200
    assert response.get_json() == {"started": "pc-tools"}

    # the worker thread runs synchronously fast enough here since the
    # monkeypatched functions return immediately; give it a moment to finish.
    import time

    for _ in range(50):
        if not webapp._running:
            break
        time.sleep(0.01)

    log_response = client.get("/api/log")
    data = log_response.get_json()
    assert data["running"] is False
    assert any("ready" in line for line in data["lines"])


def test_log_output_is_html_escaped(client, monkeypatch):
    def boom(serial):
        raise RuntimeError("<script>alert(1)</script>")

    monkeypatch.setattr(webapp, "_device_serial", boom)
    monkeypatch.setattr(adb, "list_devices", lambda: [adb.Device("a", "device")])

    client.post("/api/run/cert")
    import time

    for _ in range(50):
        if not webapp._running:
            break
        time.sleep(0.01)

    log_response = client.get("/api/log")
    lines = log_response.get_json()["lines"]
    assert not any("<script>" in line for line in lines)
    assert any("&lt;script&gt;" in line for line in lines)
