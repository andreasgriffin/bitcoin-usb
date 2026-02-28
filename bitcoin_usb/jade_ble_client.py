import asyncio
import collections
import os
import platform
import re
import shutil
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any

import aioitertools
import semver
from bleak import BleakScanner
from hwilib.common import Chain
from hwilib.devices.jade import HAS_NETWORKING, JadeClient
from hwilib.devices.jadepy import jade as hwi_jade_module
from hwilib.devices.jadepy.jade import DEFAULT_BLE_DEVICE_NAME, DEFAULT_BLE_SCAN_TIMEOUT, JadeAPI
from hwilib.devices.jadepy.jade_error import JadeError
from hwilib.errors import ActionCanceledError, DeviceNotReadyError
from hwilib.hwwclient import HardwareWalletClient
from jadepy import jade_ble as jade_ble_module
from jadepy.jade_ble import JadeBleImpl as BlockstreamJadeBleImpl

DEFAULT_MAX_AUTH_ATTEMPTS = 3
DEFAULT_DISCOVERY_SCAN_TIMEOUT_SECONDS = 6.0
DEFAULT_BLE_CONNECT_TIMEOUT_SECONDS = 15.0
DEFAULT_BLE_GATT_OPERATION_TIMEOUT_SECONDS = 10.0
DEFAULT_BLE_IO_TIMEOUT_SECONDS = 60 * 60  # the user may need lots of time to unlock and confirm a tx
_IS_BT_DEVICE_PATCHED = False
_ORIGINAL_JADEPY_SUBPROCESS_RUN = jade_ble_module.subprocess.run
# Temporary per-call channel to pass a preferred BLE MAC address into the custom
# BLE transport implementation created inside JadeAPI.create_ble(...).
# We use ContextVar instead of a class/global mutable field so concurrent
# connection attempts cannot overwrite each other's preferred address.
_PREFERRED_BLE_ADDRESS: ContextVar[str | None] = ContextVar("_PREFERRED_BLE_ADDRESS", default=None)


@contextmanager
def _preferred_ble_address(address: str | None) -> Iterator[None]:
    # set() returns a token representing the previous value for this context.
    # reset(token) restores that value, which keeps state scoped to this block.
    token: Token[str | None] = _PREFERRED_BLE_ADDRESS.set(address)
    try:
        yield
    finally:
        _PREFERRED_BLE_ADDRESS.reset(token)


def _extract_jade_serial_number(device_name: str) -> str | None:
    match = re.match(
        rf"^{re.escape(DEFAULT_BLE_DEVICE_NAME)}(?:[\s_-]+(?P<serial>[A-Za-z0-9]+))?$",
        device_name,
    )
    if not match:
        return None
    return match.groupdict().get("serial")


def discover_jade_ble_devices(
    scan_timeout: float = DEFAULT_DISCOVERY_SCAN_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    devices = asyncio.run(BleakScanner.discover(timeout=max(1.0, scan_timeout)))
    discovered: list[dict[str, Any]] = []
    seen_addresses: set[str] = set()

    for dev in devices:
        name = (dev.name or "").strip()
        if not name.startswith(DEFAULT_BLE_DEVICE_NAME):
            continue

        address = str(dev.address)
        if address in seen_addresses:
            continue
        seen_addresses.add(address)

        discovered.append(
            {
                "type": "jade",
                "model": "jade_ble",
                "path": f"ble:{address}",
                "needs_pin_sent": False,
                "needs_passphrase_sent": False,
                "transport": "bluetooth",
                "bluetooth_name": name,
                "bluetooth_address": address,
                "bluetooth_serial_number": _extract_jade_serial_number(name),
            }
        )

    return discovered


def _patch_missing_bt_device_command() -> None:
    global _IS_BT_DEVICE_PATCHED
    if _IS_BT_DEVICE_PATCHED or platform.system() != "Linux" or shutil.which("bt-device"):
        return

    def _safe_subprocess_run(command: Any, *args: Any, **kwargs: Any):
        # jadepy tries to run this cleanup command unconditionally on Linux.
        # Some distros do not ship bt-device, so treat it as a no-op.
        if isinstance(command, str) and command.strip().startswith("bt-device --remove"):
            # bt-device is optional and absent on many Linux distros; skip this cleanup call.
            return subprocess.CompletedProcess(command, 0)
        return _ORIGINAL_JADEPY_SUBPROCESS_RUN(command, *args, **kwargs)

    jade_ble_module.subprocess.run = _safe_subprocess_run
    _IS_BT_DEVICE_PATCHED = True


class CompatibleJadeBleImpl(BlockstreamJadeBleImpl):
    """
    Compatibility wrapper around `jadepy`'s BLE transport.

    Why this class exists:
    - It allows selecting a specific BLE address (`preferred_ble_address`) so we
      can connect to the exact Jade found during discovery instead of re-scanning
      and potentially picking the wrong device.
    - It preserves behavior on Linux systems without `bt-device` via the
      `_patch_missing_bt_device_command` shim.
    - It keeps BLE connection behavior compatible across `bleak` versions
      (notably disconnection callback handling).

    Where it is used:
    - `JadeBleClient.__init__` patches `hwilib.devices.jadepy.jade.JadeBleImpl`
      to this class before calling `JadeAPI.create_ble(...)`.
    - `JadeAPI.create_ble(...)` then instantiates this class internally.
    """

    def __init__(
        self,
        device_name: str,
        serial_number: str | None,
        scan_timeout: int,
        loop: asyncio.AbstractEventLoop | None,
    ) -> None:
        super().__init__(device_name, serial_number, scan_timeout, loop=loop)
        # JadeAPI.create_ble(...) instantiates this class internally. Reading the
        # ContextVar here is how we inject a one-off preferred BLE address into
        # that internal object without changing external library signatures.
        self.preferred_ble_address = _PREFERRED_BLE_ADDRESS.get()
        self.client: Any | None = None
        self.inputstream: Any | None = None
        self.rx_char_handle: int | None = None
        self.write_task: asyncio.Task[Any] | None = None
        self.connect_timeout_seconds = DEFAULT_BLE_CONNECT_TIMEOUT_SECONDS
        self.gatt_operation_timeout_seconds = DEFAULT_BLE_GATT_OPERATION_TIMEOUT_SECONDS
        self.io_timeout_seconds = DEFAULT_BLE_IO_TIMEOUT_SECONDS

    async def _await_ble_operation(
        self,
        operation: Any,
        timeout_seconds: float,
        operation_name: str,
    ) -> Any:
        try:
            return await asyncio.wait_for(operation, timeout=timeout_seconds)
        except asyncio.TimeoutError as e:
            raise JadeError(
                2,
                f"BLE operation timed out: {operation_name}",
                f"Timed out after {timeout_seconds:.1f}s",
            ) from e

    async def _connect_impl(self) -> None:
        assert self.client is None

        # Incoming notifications are buffered here and consumed by _input_stream().
        inbufs: collections.deque[bytes] = collections.deque()

        async def _input_stream():
            # JadeAPI expects a byte-stream-like async iterator.
            while self.client is not None:
                while inbufs:
                    buf = inbufs.popleft()
                    for b in buf:
                        yield b
                await asyncio.sleep(0.01)
            self.inputstream = None

        self.inputstream = _input_stream()

        # Use the caller-selected BLE address when present; otherwise fall back to scanning.
        device_mac = self.preferred_ble_address
        full_name = self.device_name
        if not device_mac:
            while not device_mac and self.scan_timeout > 0:
                jade_ble_module.logger.info(f"Scanning, timeout = {self.scan_timeout}s")
                scan_time = min(2, self.scan_timeout)
                self.scan_timeout -= scan_time

                devices = await self._await_ble_operation(
                    BleakScanner.discover(timeout=scan_time),
                    timeout_seconds=float(scan_time) + self.gatt_operation_timeout_seconds,
                    operation_name="discover",
                )
                for dev in devices:
                    jade_ble_module.logger.debug(f"Seen: {dev.name}")
                    if (
                        dev.name
                        and dev.name.startswith(self.device_name)
                        and (self.serial_number is None or dev.name.endswith(self.serial_number))
                    ):
                        device_mac = dev.address
                        full_name = dev.name

        if not device_mac:
            raise JadeError(
                1,
                "Unable to locate BLE device",
                f"Device name: {self.device_name}, Serial number: {self.serial_number or '<any>'}",
            )

        if platform.system() == "Linux":
            # Remove stale BlueZ pairing state if present. Missing bt-device is handled by the patch above.
            command = f'bt-device --remove "{device_mac}"'
            jade_ble_module.subprocess.run(command, shell=True, stdout=subprocess.DEVNULL)

        def _disconnection_handler(client: Any) -> None:
            assert client == self.client
            self.client = None
            if self.write_task:
                self.write_task.cancel()
                self.write_task = None

        connected = False
        attempts_remaining = 5
        client = None
        needs_set_disconnection_callback = False
        attempted_windows_unpair = False
        # Bleak connect can fail transiently; retry a few times before giving up.
        while not connected:
            try:
                attempts_remaining -= 1
                try:
                    client = jade_ble_module.bleak.BleakClient(
                        device_mac, disconnected_callback=_disconnection_handler
                    )
                except TypeError:
                    client = jade_ble_module.bleak.BleakClient(device_mac)
                    needs_set_disconnection_callback = True

                jade_ble_module.logger.info(f"Connecting to: {full_name} ({device_mac})")
                await self._await_ble_operation(
                    client.connect(),
                    timeout_seconds=self.connect_timeout_seconds,
                    operation_name="connect",
                )
                connected = client.is_connected
                jade_ble_module.logger.info(f"Connected: {connected}")
            except Exception as e:
                jade_ble_module.logger.warning(f"BLE connection exception: {e}")
                if platform.system() == "Windows" and not attempted_windows_unpair:
                    attempted_windows_unpair = True
                    unpaired = await self._try_unpair_windows_device(device_mac=device_mac)
                    if unpaired:
                        jade_ble_module.logger.info(
                            "Removed Windows pairing state for %s; retrying BLE connect",
                            device_mac,
                        )

                if not attempts_remaining:
                    jade_ble_module.logger.warning("Exhausted retries - BLE connection failed")
                    raise JadeError(
                        2,
                        "Unable to connect to BLE device",
                        f"Device name: {self.device_name}, Serial number: {self.serial_number or '<any>'}",
                    ) from e

        if client is None:
            raise JadeError(
                2,
                "Unable to connect to BLE device",
                f"Device name: {self.device_name}, Serial number: {self.serial_number or '<any>'}",
            )

        connected_client = client
        # Probe services/chars/descriptors up front to make sure handles are ready.
        for service in connected_client.services:
            for char in service.characteristics:
                if char.uuid == BlockstreamJadeBleImpl.IO_RX_CHAR_UUID:
                    jade_ble_module.logger.debug(f"Found RX characteristic - handle: {char.handle}")
                    self.rx_char_handle = char.handle

                if "read" in char.properties:
                    await self._await_ble_operation(
                        connected_client.read_gatt_char(char.uuid),
                        timeout_seconds=self.gatt_operation_timeout_seconds,
                        operation_name="read_gatt_char",
                    )

                for descriptor in char.descriptors:
                    await self._await_ble_operation(
                        connected_client.read_gatt_descriptor(descriptor.handle),
                        timeout_seconds=self.gatt_operation_timeout_seconds,
                        operation_name="read_gatt_descriptor",
                    )

        def _notification_handler(sender: Any, data: Any) -> None:
            # bleak may pass sender either as an int handle or as a characteristic object.
            sender_handle = -1
            if isinstance(sender, int):
                sender_handle = sender
            else:
                try:
                    sender_handle = int(sender.handle)
                except Exception:
                    return

            if sender_handle != self.rx_char_handle:
                return
            inbufs.append(bytes(data))

        assert self.rx_char_handle
        await self._await_ble_operation(
            connected_client.start_notify(self.rx_char_handle, _notification_handler),
            timeout_seconds=self.gatt_operation_timeout_seconds,
            operation_name="start_notify",
        )

        if needs_set_disconnection_callback:
            connected_client.set_disconnected_callback(_disconnection_handler)

        self.client = connected_client

    async def _try_unpair_windows_device(self, device_mac: str) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            unpair_client = jade_ble_module.bleak.BleakClient(device_mac)
        except Exception as e:
            jade_ble_module.logger.warning("Unable to prepare Windows BLE unpair client: %s", e)
            return False

        try:
            result = await self._await_ble_operation(
                unpair_client.unpair(),
                timeout_seconds=self.gatt_operation_timeout_seconds,
                operation_name="unpair",
            )
            return bool(result)
        except Exception as e:
            jade_ble_module.logger.warning("Windows BLE unpair failed for %s: %s", device_mac, e)
            return False

    async def _disconnect_impl(self) -> None:
        try:
            if self.client is not None and self.client.is_connected:
                if self.rx_char_handle:
                    await self._await_ble_operation(
                        self.client.stop_notify(self.rx_char_handle),
                        timeout_seconds=self.gatt_operation_timeout_seconds,
                        operation_name="stop_notify",
                    )
                await self._await_ble_operation(
                    self.client.disconnect(),
                    timeout_seconds=self.gatt_operation_timeout_seconds,
                    operation_name="disconnect",
                )
        except Exception as err:
            jade_ble_module.logger.warning(f"Exception when disconnecting ble: {err}")

        self.rx_char_handle = None
        self.client = None
        if self.write_task:
            self.write_task.cancel()
            self.write_task = None

    async def _write_impl(self, bytes_: bytes) -> int:  # type: ignore
        assert self.client is not None
        assert self.write_task is None

        towrite = len(bytes_)
        written = 0

        async def _write() -> None:
            if self.client is None:
                return
            nonlocal written

            while written < towrite:
                remaining = towrite - written
                length = min(remaining, BlockstreamJadeBleImpl.BLE_MAX_WRITE_SIZE)
                upper_limit = written + length
                await self.client.write_gatt_char(
                    BlockstreamJadeBleImpl.IO_TX_CHAR_UUID,
                    bytearray(bytes_[written:upper_limit]),
                    response=True,
                )
                written = upper_limit

        self.write_task = asyncio.create_task(_write())
        try:
            await self._await_ble_operation(
                self.write_task,
                timeout_seconds=self.io_timeout_seconds,
                operation_name="write",
            )
        except asyncio.CancelledError:
            jade_ble_module.logger.warning(
                "write() task cancelled having written %d of %d bytes", written, towrite
            )
        finally:
            self.write_task = None

        return written

    async def _read_impl(self, n: int) -> bytes:
        assert self.inputstream is not None
        return await self._await_ble_operation(
            self._read_bytes_from_stream(n=n),
            timeout_seconds=self.io_timeout_seconds,
            operation_name=f"read({n})",
        )

    async def _read_bytes_from_stream(self, n: int) -> bytes:
        assert self.inputstream is not None
        return bytes([b async for b in aioitertools.islice(self.inputstream, n)])  # type: ignore


class JadeBleClient(JadeClient):
    """
    HWI Jade client variant that connects over Bluetooth LE.

    Why this class exists:
    - Upstream `JadeClient` expects transport setup from HWI, but this project
      needs explicit BLE-device selection from GUI discovery results.
    - It injects `CompatibleJadeBleImpl` so `JadeAPI.create_ble(...)` uses the
      custom transport behavior defined in this module.
    - It owns a dedicated asyncio loop for BLE operations and performs the Jade
      firmware/auth initialization sequence used by the rest of `USBDevice`.

    Where it is used:
    - `bitcoin_usb/device.py` instantiates `JadeBleClient` when a selected
      device has `transport == "bluetooth"` and `type == "jade"`.
    """

    def __init__(
        self,
        device_name: str,
        serial_number: str | None,
        device_address: str | None = None,
        password: str | None = None,
        expert: bool = False,
        chain: Chain = Chain.MAIN,
        scan_timeout: int = DEFAULT_BLE_SCAN_TIMEOUT,
        max_auth_attempts: int = DEFAULT_MAX_AUTH_ATTEMPTS,
    ) -> None:
        _patch_missing_bt_device_command()
        hwi_jade_module_any: Any = hwi_jade_module
        # Force HWI's jade module to use our compatible BLE transport implementation.
        hwi_jade_module_any.JadeBleImpl = CompatibleJadeBleImpl

        path = f"ble:{device_name}:{serial_number or ''}"
        HardwareWalletClient.__init__(self, path, password, expert, chain)
        self.jade: JadeAPI | None = None

        # Keep BLE traffic on a dedicated loop so this client can run independently.
        self._ble_loop = asyncio.new_event_loop()
        try:
            # Scope the preferred address override to object construction only.
            # CompatibleJadeBleImpl.__init__ reads it during create_ble(...), then
            # the context manager restores the previous value immediately.
            with _preferred_ble_address(device_address):
                self.jade = JadeAPI.create_ble(
                    device_name=device_name,
                    serial_number=serial_number,
                    scan_timeout=scan_timeout,
                    loop=self._ble_loop,
                )
            self.jade.connect()
            self._initialize_device(max_auth_attempts=max_auth_attempts)
        except Exception:
            self._disconnect_and_close_loop()
            raise

    def _initialize_device(self, max_auth_attempts: int) -> None:
        assert self.jade is not None

        # Validate firmware/version and current wallet state before doing auth.
        verinfo = self.jade.get_version_info()
        self.fw_version = semver.parse_version_info(verinfo["JADE_VERSION"])
        uninitialized = verinfo["JADE_STATE"] not in ["READY", "TEMP"]

        if self.MIN_SUPPORTED_FW_VERSION > self.fw_version.finalize_version():
            raise DeviceNotReadyError(
                f"Jade fw version: {self.fw_version} - minimum required version: "
                f"{self.MIN_SUPPORTED_FW_VERSION}. Please update using a Blockstream Green companion app"
            )

        if uninitialized and not HAS_NETWORKING:
            raise DeviceNotReadyError(
                'Use "Recovery Phrase Login" or "QR PIN Unlock" feature on Jade hw to access wallet'
            )

        self.jade.add_entropy(os.urandom(32))

        # Auth may fail/cancel repeatedly; cap retries to avoid infinite loops.
        failed_attempts = 0
        while True:
            try:
                authenticated = self.jade.auth_user(self._network())
            except JadeError as e:
                if e.code == JadeError.USER_CANCELLED:
                    raise ActionCanceledError(
                        "Jade connection/authentication was canceled by the user"
                    ) from e
                raise

            if authenticated:
                return

            failed_attempts += 1
            if failed_attempts >= max_auth_attempts:
                raise ActionCanceledError("Jade connection/authentication was denied or failed repeatedly")

    def _disconnect_and_close_loop(self) -> None:
        # Best-effort shutdown: disconnect device first, then close event loop.
        if self.jade is not None:
            try:
                self.jade.disconnect()
            except Exception:
                pass
            finally:
                self.jade = None
        if not self._ble_loop.is_closed():
            self._ble_loop.close()

    def close(self) -> None:
        self._disconnect_and_close_loop()
