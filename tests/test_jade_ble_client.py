import asyncio

import pytest
from hwilib.devices.jadepy.jade_error import JadeError

from bitcoin_usb.jade_ble_client import CompatibleJadeBleImpl


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
