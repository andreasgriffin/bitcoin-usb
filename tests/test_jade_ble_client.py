import asyncio

import pytest
from hwilib.devices.jadepy.jade_error import JadeError

from bitcoin_usb.jade_ble_client import (
    CompatibleJadeBleImpl,
    _SafeBleakCallbackLoop,
    _protect_corebluetooth_client_callback_loops,
    _scan_ble_devices_async,
    discover_jade_ble_devices,
)


async def _never_stream():
    while True:
        await asyncio.sleep(1)
        if False:
            yield 0  # type: ignore


class _SlowGattClient:
    async def write_gatt_char(self, uuid, payload, response):
        _ = uuid
        _ = payload
        _ = response
        await asyncio.sleep(1)


def test_read_impl_times_out() -> None:
    loop = asyncio.new_event_loop()
    client = CompatibleJadeBleImpl(device_name="Jade", serial_number=None, scan_timeout=1, loop=loop)
    client.inputstream = _never_stream()
    client.io_timeout_seconds = 0.01

    with pytest.raises(JadeError, match="BLE operation timed out: read\\(1\\)"):
        loop.run_until_complete(client._read_impl(1))

    loop.run_until_complete(client.inputstream.aclose())
    loop.close()


def test_write_impl_times_out() -> None:
    loop = asyncio.new_event_loop()
    client = CompatibleJadeBleImpl(device_name="Jade", serial_number=None, scan_timeout=1, loop=loop)
    client.client = _SlowGattClient()
    client.io_timeout_seconds = 0.01

    with pytest.raises(JadeError, match="BLE operation timed out: write"):
        loop.run_until_complete(client._write_impl(b"abc"))

    assert client.write_task is None
    loop.close()


def test_discover_jade_ble_devices_uses_existing_loop(monkeypatch) -> None:
    class _Device:
        def __init__(self, name: str, address: str) -> None:
            self.name = name
            self.address = address

    captured: dict[str, object] = {}
    loop_in_thread = object()

    def fake_scan_ble_devices(loop, scan_timeout):
        captured["loop"] = loop
        captured["scan_timeout"] = scan_timeout
        return [
            _Device("Jade ABC123", "AA:BB"),
            _Device("Jade ABC123", "AA:BB"),
            _Device("Other Device", "CC:DD"),
        ]

    monkeypatch.setattr("bitcoin_usb.jade_ble_client.scan_ble_devices", fake_scan_ble_devices)

    assert discover_jade_ble_devices(loop_in_thread, scan_timeout=2.5) == [
        {
            "type": "jade",
            "model": "jade_ble",
            "path": "ble:AA:BB",
            "needs_pin_sent": False,
            "needs_passphrase_sent": False,
            "transport": "bluetooth",
            "bluetooth_name": "Jade ABC123",
            "bluetooth_address": "AA:BB",
            "bluetooth_serial_number": "ABC123",
        }
    ]
    assert captured["loop"] is loop_in_thread
    assert captured["scan_timeout"] == 2.5


def test_safe_bleak_callback_loop_ignores_closed_loop_callbacks() -> None:
    loop = asyncio.new_event_loop()
    wrapped = _SafeBleakCallbackLoop(loop)
    loop.close()

    wrapped.call_soon_threadsafe(lambda: None)


def test_scan_ble_devices_async_wraps_darwin_manager_loop(monkeypatch) -> None:
    class _Manager:
        def __init__(self) -> None:
            self.event_loop = asyncio.new_event_loop()

    manager = _Manager()
    manager_loop = manager.event_loop

    class _Backend:
        def __init__(self) -> None:
            self._manager = manager

    class _Scanner:
        def __init__(self) -> None:
            self._backend = _Backend()
            self.discovered_devices = ["device"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    async def _fake_sleep(_timeout: float) -> None:
        return None

    monkeypatch.setattr("bitcoin_usb.jade_ble_client.platform.system", lambda: "Darwin")
    monkeypatch.setattr("bitcoin_usb.jade_ble_client.BleakScanner", _Scanner)
    monkeypatch.setattr("bitcoin_usb.jade_ble_client.asyncio.sleep", _fake_sleep)

    loop = asyncio.new_event_loop()
    try:
        assert loop.run_until_complete(_scan_ble_devices_async(0.2)) == ["device"]
    finally:
        loop.close()
        manager_loop.close()

    assert isinstance(manager.event_loop, _SafeBleakCallbackLoop)


def test_protect_corebluetooth_client_callback_loops_wraps_manager_and_delegate(
    monkeypatch,
) -> None:
    class _Manager:
        def __init__(self) -> None:
            self.event_loop = asyncio.new_event_loop()

    class _Delegate:
        def __init__(self) -> None:
            self._event_loop = asyncio.new_event_loop()

    class _Backend:
        def __init__(self) -> None:
            self._central_manager_delegate = _Manager()
            self._delegate = _Delegate()

    class _Client:
        def __init__(self) -> None:
            self._backend = _Backend()

    client = _Client()
    manager_loop = client._backend._central_manager_delegate.event_loop
    delegate_loop = client._backend._delegate._event_loop

    monkeypatch.setattr("bitcoin_usb.jade_ble_client.platform.system", lambda: "Darwin")

    try:
        _protect_corebluetooth_client_callback_loops(client)
    finally:
        manager_loop.close()
        delegate_loop.close()

    assert isinstance(client._backend._central_manager_delegate.event_loop, _SafeBleakCallbackLoop)
    assert isinstance(client._backend._delegate._event_loop, _SafeBleakCallbackLoop)
