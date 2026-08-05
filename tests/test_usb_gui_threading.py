from types import SimpleNamespace

import bdkpython as bdk
import pytest

from bitcoin_usb.device import USBDevice
from bitcoin_usb.usb_gui import USBGui


def test_usbdevice_enter_is_synchronous(monkeypatch) -> None:
    init_calls: list[str] = []

    def fake_init_client(self: USBDevice) -> None:
        init_calls.append("called")

    monkeypatch.setattr(USBDevice, "_init_client", fake_init_client)

    device = USBDevice(
        selected_device={"type": "jade", "path": "/dev/mock"},
        network=bdk.Network.REGTEST,
        loop_in_thread=object(),
        initalization_label="",
    )
    with device as entered_device:
        assert entered_device is device

    assert init_calls == ["called"]


def test_usbdevice_run_wrapper_removed() -> None:
    assert not hasattr(USBDevice, "run")


def test_usbdevice_execute_with_client_removed() -> None:
    assert not hasattr(USBDevice, "execute_with_client")


def test_usbgui_with_device_exists() -> None:
    assert hasattr(USBGui, "_with_device")


def test_usbgui_run_with_device_wrapper_removed() -> None:
    assert not hasattr(USBGui, "_run_with_device")


def test_trezor_firmware_update_stops_initialization_after_reboot(monkeypatch) -> None:
    firmware_calls: list[tuple[object, list[str]]] = []

    class FakeTrezorClient:
        def __init__(self) -> None:
            self.client = SimpleNamespace(
                refresh_features=lambda: None,
                features=SimpleNamespace(bootloader_mode=True, initialized=False),
            )

    fake_client = FakeTrezorClient()

    def fake_run_script(filepath: object, args: list[str]) -> tuple[str, str]:
        firmware_calls.append((filepath, args))
        return "", ""

    monkeypatch.setattr("bitcoin_usb.device.TrezorClient", FakeTrezorClient)
    monkeypatch.setattr("bitcoin_usb.device.hwi_commands.get_client", lambda **kwargs: fake_client)
    monkeypatch.setattr("bitcoin_usb.device.run_script", fake_run_script)
    monkeypatch.setattr(
        "bitcoin_usb.device.question_dialog",
        lambda *args, **kwargs: pytest.fail("Initialization dialog must not open after a reboot"),
    )

    device = USBDevice(
        selected_device={"type": "trezor", "path": "webusb:001"},
        network=bdk.Network.BITCOIN,
    )

    with pytest.raises(RuntimeError, match="firmware update finished.*reconnect"):
        device._init_client()

    assert len(firmware_calls) == 1
    assert firmware_calls[0][1] == ["--path", "webusb:001"]
