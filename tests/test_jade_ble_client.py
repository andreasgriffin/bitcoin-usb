import asyncio

import pytest
from hwilib.devices.jadepy.jade_error import JadeError

from bitcoin_usb.jade_ble_client import CompatibleJadeBleImpl, discover_jade_ble_devices


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

    monkeypatch.setattr(
        "bitcoin_usb.jade_ble_client.BleakScanner.discover",
        lambda timeout: {"timeout": timeout},
    )

    class _LoopInThread:
        def run_foreground(self, coroutine):
            captured["discover_call"] = coroutine
            return [
                _Device("Jade ABC123", "AA:BB"),
                _Device("Jade ABC123", "AA:BB"),
                _Device("Other Device", "CC:DD"),
            ]

    loop_in_thread = _LoopInThread()

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
    assert captured["discover_call"] == {"timeout": 2.5}
