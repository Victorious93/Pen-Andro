"""Shared pytest fixtures.

Only `real_device_serial` lives here — everything else in the suite mocks
the adb/shell/requests boundary and needs no fixture at all. This fixture
exists solely to gate the opt-in tests in test_device_integration.py.
"""
from __future__ import annotations

import os

import pytest

from pen_andro import adb


def _has_real_device() -> bool:
    try:
        return any(device.state == "device" for device in adb.list_devices())
    except Exception:
        return False


@pytest.fixture(scope="session")
def real_device_serial() -> str:
    """Serial of a connected, rooted device — skips the test if unavailable.

    Opt-in: set PEN_ANDRO_RUN_DEVICE_TESTS=1 and connect a real device
    before running `pytest -m device`. Without both, every test using this
    fixture is skipped, so the default `pytest` run stays hermetic.
    """
    if os.environ.get("PEN_ANDRO_RUN_DEVICE_TESTS") != "1":
        pytest.skip("set PEN_ANDRO_RUN_DEVICE_TESTS=1 to run tests against a real device")
    if not _has_real_device():
        pytest.skip("no adb device connected")
    return adb.resolve_device().serial
