import threading
import time
from types import SimpleNamespace
from typing import Any, cast

import bdkpython as bdk
from hwilib.common import Chain
import hwilib.devices.trezorlib.messages as hwi_messages
from hwilib.key import ExtendedKey
from PyQt6.QtCore import QCoreApplication
import trezorlib.messages as trezor_messages

from bitcoin_usb.device import USBDevice, bdknetwork_to_chain
from bitcoin_usb.trezor_thp import (
    TrezorThpClient,
    _HwiMessageBridge,
    _HwiTrezorSessionAdapter,
    _enumerate_trezor_transports,
    _request_text,
)
from bitcoin_usb.usb_gui import USBGui, enumerate_available_devices


def _trezor_features(model: str) -> trezor_messages.Features:
    return trezor_messages.Features(
        model=model,
        major_version=2,
        minor_version=8,
        patch_version=0,
    )


def test_enumerate_available_devices_merges_trezor_thp(monkeypatch) -> None:
    hwi_devices = [
        {"type": "jade", "path": "usb:1"},
        {"type": "trezor", "path": "webusb:001", "model": "unknown"},
    ]
    thp_devices = [
        {"type": "trezor", "path": "webusb:001", "model": "Safe 7", "protocol": "thp"},
    ]

    monkeypatch.setattr("hwilib.commands.enumerate", lambda allow_emulators=False, chain=None: hwi_devices)
    monkeypatch.setattr(
        "bitcoin_usb.usb_gui.enumerate_trezor_thp_devices",
        lambda: thp_devices,
    )

    devices = enumerate_available_devices(
        allow_emulators=False,
        chain=bdknetwork_to_chain(bdk.Network.BITCOIN),
    )

    assert {"type": "jade", "path": "usb:1"} in devices
    assert {"type": "trezor", "path": "webusb:001", "model": "Safe 7", "protocol": "thp"} in devices
    assert len(devices) == 2


def test_enumerate_trezor_transports_skips_ble(monkeypatch) -> None:
    calls: list[str] = []

    class FakeTransport:
        def __init__(self, path: str) -> None:
            self._path = path

        def get_path(self) -> str:
            return self._path

        def close(self) -> None:
            return None

    class FakeBleTransport:
        PATH_PREFIX = "ble"
        __name__ = "FakeBleTransport"

        @classmethod
        def enumerate(cls) -> list[FakeTransport]:
            calls.append(cls.PATH_PREFIX)
            raise AssertionError("BLE transport should not be enumerated")

    class FakeWebUsbTransport:
        PATH_PREFIX = "webusb"
        __name__ = "FakeWebUsbTransport"

        @classmethod
        def enumerate(cls) -> list[FakeTransport]:
            calls.append(cls.PATH_PREFIX)
            return [FakeTransport("webusb:001")]

    monkeypatch.setattr(
        "bitcoin_usb.trezor_thp.trezorlib_all_transports",
        lambda: [FakeBleTransport, FakeWebUsbTransport],
    )

    transports = _enumerate_trezor_transports()

    assert calls == ["webusb"]
    assert [transport.get_path() for transport in transports] == ["webusb:001"]


def test_trezor_thp_devices_run_inline() -> None:
    selected_device = {"type": "trezor", "path": "webusb:001", "protocol": "thp"}
    assert USBGui._should_run_in_worker(selected_device) is True


def test_trezor_safe7_v1_devices_run_inline() -> None:
    selected_device = {"type": "trezor", "path": "webusb:001", "protocol": "v1", "internal_model": "T3W1"}
    assert USBGui._should_run_in_worker(selected_device) is True


def test_modern_trezor_devices_can_be_forced_inline(monkeypatch) -> None:
    selected_device = {"type": "trezor", "path": "webusb:001", "protocol": "thp"}
    monkeypatch.setattr("bitcoin_usb.usb_gui.MODERN_TREZOR_USE_WORKER_THREAD", False)
    assert USBGui._should_run_in_worker(selected_device) is False


def test_trezor_prompt_requests_use_main_thread(monkeypatch) -> None:
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])

    main_thread_ident = threading.get_ident()
    captured: dict[str, object] = {}
    result: dict[str, str] = {}
    errors: list[Exception] = []

    def fake_show_text_dialog(title: str, label: str, echo) -> str:
        captured["title"] = title
        captured["label"] = label
        captured["thread_ident"] = threading.get_ident()
        return "123456"

    monkeypatch.setattr("bitcoin_usb.trezor_thp._show_text_dialog", fake_show_text_dialog)

    def run_request() -> None:
        try:
            result["value"] = _request_text("Pair Trezor", "Enter code")
        except Exception as exc:  # pragma: no cover - assertion below reports failures
            errors.append(exc)

    worker = threading.Thread(target=run_request)
    worker.start()

    deadline = time.monotonic() + 2.0
    while worker.is_alive() and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)

    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert not errors
    assert result["value"] == "123456"
    assert captured["title"] == "Pair Trezor"
    assert captured["label"] == "Enter code"
    assert captured["thread_ident"] == main_thread_ident


def test_trezor_thp_sign_tx_reuses_hwi_sign_tx(monkeypatch) -> None:
    client = object.__new__(TrezorThpClient)
    client.chain = Chain.MAIN
    client.password = ""
    client.type = "Trezor"
    client.client = SimpleNamespace(
        version=(2, 8, 0),
        features=SimpleNamespace(model="T"),
    )

    fake_session = object()

    class FakeSessionContext:
        def __enter__(self):
            return fake_session

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            return None

    client._wallet_session = lambda: FakeSessionContext()  # type: ignore[method-assign]
    captured: dict[str, object] = {}

    def fake_sign_tx(adapter, psbt):
        captured["adapter"] = adapter
        captured["psbt"] = psbt
        return "signed"

    monkeypatch.setattr("bitcoin_usb.trezor_thp.HwiTrezorClient.sign_tx", fake_sign_tx)

    assert client.sign_tx("psbt") == "signed"
    assert captured["psbt"] == "psbt"
    assert cast(Any, captured["adapter"]).client._session is fake_session


def test_hwi_message_bridge_converts_between_protobuf_stacks() -> None:
    captured: dict[str, object] = {}

    class FakeSession:
        def call(self, message):
            captured["request_type"] = type(message)
            return trezor_messages.Success(message="ok")

    bridge = _HwiMessageBridge(FakeSession(), _trezor_features("T"), (2, 8, 0))
    request = hwi_messages.GetPublicKey(
        address_n=[1, 2, 3],
        coin_name="Bitcoin",
    )

    response = bridge.call(request)

    assert captured["request_type"].__module__ == "trezorlib.messages"
    assert type(response).__module__ == "hwilib.devices.trezorlib.messages"
    assert response.message == "ok"


def test_hwi_message_bridge_open_close_are_noops() -> None:
    bridge = _HwiMessageBridge(
        object(),
        _trezor_features("T"),
        (2, 8, 0),
    )
    bridge.open()
    bridge.close()


def test_trezor_thp_supports_external_reuses_hwi_logic(monkeypatch) -> None:
    client = object.__new__(TrezorThpClient)
    client.chain = Chain.MAIN
    client.password = ""
    client.type = "Trezor"
    client.client = SimpleNamespace(
        version=(2, 8, 0),
        features=_trezor_features("T"),
    )

    fake_session = object()

    captured: dict[str, object] = {}

    def fake_supports_external(adapter) -> bool:
        captured["adapter"] = adapter
        captured["model"] = adapter.client.features.model
        captured["version"] = adapter.client.version
        return True

    monkeypatch.setattr("bitcoin_usb.trezor_thp.HwiTrezorClient._supports_external", fake_supports_external)

    assert client.client.features is not None
    assert client.client.version == (2, 8, 0)

    adapter = _HwiTrezorSessionAdapter(client, fake_session)

    assert adapter._supports_external() is True
    assert captured["adapter"] is adapter
    assert captured["model"] == "T"
    assert captured["version"] == (2, 8, 0)


def test_trezor_thp_get_pubkey_reuses_hwi(monkeypatch) -> None:
    client = object.__new__(TrezorThpClient)
    client.chain = Chain.MAIN
    client.password = ""
    client.type = "Trezor"
    client.client = SimpleNamespace(
        version=(2, 8, 0),
        features=SimpleNamespace(model="T"),
    )

    fake_session = object()

    class FakeSessionContext:
        def __enter__(self):
            return fake_session

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            return None

    client._wallet_session = lambda: FakeSessionContext()  # type: ignore[method-assign]
    captured: dict[str, object] = {}
    expected = ExtendedKey(
        version=ExtendedKey.MAINNET_PUBLIC,
        depth=0,
        parent_fingerprint=b"\x00\x00\x00\x00",
        child_num=0,
        chaincode=b"\x11" * 32,
        privkey=None,
        pubkey=b"\x02" + b"\x22" * 32,
    )

    def fake_get_pubkey_at_path(adapter, bip32_path):
        captured["adapter"] = adapter
        captured["bip32_path"] = bip32_path
        return expected

    monkeypatch.setattr("bitcoin_usb.trezor_thp.HwiTrezorClient.get_pubkey_at_path", fake_get_pubkey_at_path)

    assert client.get_pubkey_at_path("m/84h/0h/0h") is expected
    assert captured["bip32_path"] == "m/84h/0h/0h"
    assert cast(Any, captured["adapter"]).client._session is fake_session


def test_trezor_thp_sign_message_reuses_hwi(monkeypatch) -> None:
    client = object.__new__(TrezorThpClient)
    client.chain = Chain.MAIN
    client.password = ""
    client.type = "Trezor"
    client.client = SimpleNamespace(
        version=(2, 8, 0),
        features=SimpleNamespace(model="T"),
    )

    fake_session = object()

    class FakeSessionContext:
        def __enter__(self):
            return fake_session

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            return None

    client._wallet_session = lambda: FakeSessionContext()  # type: ignore[method-assign]
    captured: dict[str, object] = {}

    def fake_sign_message(adapter, message, bip32_path):
        captured["adapter"] = adapter
        captured["message"] = message
        captured["bip32_path"] = bip32_path
        return "signature"

    monkeypatch.setattr("bitcoin_usb.trezor_thp.HwiTrezorClient.sign_message", fake_sign_message)

    assert client.sign_message("hello", "m/84h/0h/0h/0/0") == "signature"
    assert captured["message"] == "hello"
    assert captured["bip32_path"] == "m/84h/0h/0h/0/0"
    assert cast(Any, captured["adapter"]).client._session is fake_session


def test_trezor_thp_display_multisig_reuses_hwi(monkeypatch) -> None:
    client = object.__new__(TrezorThpClient)
    client.chain = Chain.MAIN
    client.password = ""
    client.type = "Trezor"
    client.client = SimpleNamespace(
        version=(2, 8, 0),
        features=SimpleNamespace(model="T"),
    )

    fake_session = object()

    class FakeSessionContext:
        def __enter__(self):
            return fake_session

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            return None

    client._wallet_session = lambda: FakeSessionContext()  # type: ignore[method-assign]
    captured: dict[str, object] = {}

    def fake_display_multisig_address(adapter, addr_type, multisig):
        captured["adapter"] = adapter
        captured["addr_type"] = addr_type
        captured["multisig"] = multisig
        return "bc1test"

    monkeypatch.setattr(
        "bitcoin_usb.trezor_thp.HwiTrezorClient.display_multisig_address",
        fake_display_multisig_address,
    )

    assert client.display_multisig_address("addr_type", "multisig") == "bc1test"
    assert captured["addr_type"] == "addr_type"
    assert captured["multisig"] == "multisig"
    assert cast(Any, captured["adapter"]).client._session is fake_session


def test_trezor_thp_display_singlesig_reuses_hwi(monkeypatch) -> None:
    client = object.__new__(TrezorThpClient)
    client.chain = Chain.MAIN
    client.password = ""
    client.type = "Trezor"
    client.client = SimpleNamespace(
        version=(2, 8, 0),
        features=SimpleNamespace(model="T"),
    )

    fake_session = object()

    class FakeSessionContext:
        def __enter__(self):
            return fake_session

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            return None

    client._wallet_session = lambda: FakeSessionContext()  # type: ignore[method-assign]
    captured: dict[str, object] = {}

    def fake_display_singlesig_address(adapter, bip32_path, addr_type):
        captured["adapter"] = adapter
        captured["bip32_path"] = bip32_path
        captured["addr_type"] = addr_type
        return "bc1single"

    monkeypatch.setattr(
        "bitcoin_usb.trezor_thp.HwiTrezorClient.display_singlesig_address",
        fake_display_singlesig_address,
    )

    assert client.display_singlesig_address("m/84h/0h/0h/0/0", "addr_type") == "bc1single"
    assert captured["bip32_path"] == "m/84h/0h/0h/0/0"
    assert captured["addr_type"] == "addr_type"
    assert cast(Any, captured["adapter"]).client._session is fake_session


def test_usb_device_uses_trezor_thp_client(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeTrezorThpClient:
        def __init__(self, path: str, password=None, expert: bool = False, chain=None) -> None:
            captured["path"] = path
            captured["expert"] = expert
            captured["chain"] = chain

        def refresh_features(self):
            return SimpleNamespace(bootloader_mode=False, initialized=True)

        @property
        def features(self):
            return SimpleNamespace(bootloader_mode=False, initialized=True)

    def fail_get_client(*args, **kwargs):
        raise AssertionError("HWI get_client should not be used for THP devices")

    monkeypatch.setattr("bitcoin_usb.device.TrezorThpClient", FakeTrezorThpClient)
    monkeypatch.setattr("bitcoin_usb.device.hwi_commands.get_client", fail_get_client)

    device = USBDevice(
        selected_device={"type": "trezor", "path": "webusb:001", "protocol": "thp"},
        network=bdk.Network.BITCOIN,
    )
    device._init_client()

    assert captured == {
        "path": "webusb:001",
        "expert": False,
        "chain": bdknetwork_to_chain(bdk.Network.BITCOIN),
    }


def test_usb_device_uses_local_trezor_client_for_safe7_v1(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeTrezorThpClient:
        def __init__(self, path: str, password=None, expert: bool = False, chain=None) -> None:
            captured["path"] = path
            captured["expert"] = expert
            captured["chain"] = chain

        def refresh_features(self):
            return SimpleNamespace(bootloader_mode=False, initialized=True)

        @property
        def features(self):
            return SimpleNamespace(bootloader_mode=False, initialized=True)

    def fail_get_client(*args, **kwargs):
        raise AssertionError("HWI get_client should not be used for Safe 7 v1 devices")

    monkeypatch.setattr("bitcoin_usb.device.TrezorThpClient", FakeTrezorThpClient)
    monkeypatch.setattr("bitcoin_usb.device.hwi_commands.get_client", fail_get_client)

    device = USBDevice(
        selected_device={
            "type": "trezor",
            "path": "webusb:001",
            "protocol": "v1",
            "internal_model": "T3W1",
        },
        network=bdk.Network.BITCOIN,
    )
    device._init_client()

    assert captured == {
        "path": "webusb:001",
        "expert": False,
        "chain": bdknetwork_to_chain(bdk.Network.BITCOIN),
    }
