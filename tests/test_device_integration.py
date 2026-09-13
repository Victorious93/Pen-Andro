"""Integration tests that exercise real adb/device behavior end to end.

Skipped by default (see conftest.py's real_device_serial fixture). To run
these against a connected, rooted device or emulator:

    PEN_ANDRO_RUN_DEVICE_TESTS=1 pytest -m device

These intentionally do NOT install/modify anything on the device (no cert,
no frida-server, no apps) — they only assert on read-only state, so running
them against a real test device is safe to repeat.
"""
import pytest

from pen_andro import adb, frida_tools, network

pytestmark = pytest.mark.device


def test_root_access_is_granted(real_device_serial):
    assert adb.check_root(real_device_serial) is True


def test_device_arch_resolves_to_a_known_frida_target(real_device_serial):
    assert frida_tools.device_arch(real_device_serial) in set(frida_tools.ARCH_MAP.values())


def test_internet_is_reachable(real_device_serial):
    # doesn't use the serial, but depends on the fixture so this test is
    # gated by the same PEN_ANDRO_RUN_DEVICE_TESTS opt-in as the others
    # instead of running unconditionally whenever -m device is passed.
    del real_device_serial
    assert network.has_internet() is True
