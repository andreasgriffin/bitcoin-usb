import bdkpython as bdk

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
