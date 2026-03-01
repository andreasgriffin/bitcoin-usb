from bitcoin_usb import usb_gui
from bitcoin_usb.usb_gui import USBGui


def test_can_scan_bluetooth_devices_uses_ble_operation_wrapper(monkeypatch) -> None:
    calls: dict[str, bool] = {"wrapped": False, "run_called": False}

    monkeypatch.setattr(usb_gui, "is_ble_available", lambda: True)
    monkeypatch.setattr(usb_gui.BleakScanner, "discover", lambda timeout: "probe")

    def fake_run_ble_operation(operation):
        calls["wrapped"] = True
        return operation()

    def fake_asyncio_run(_probe):
        calls["run_called"] = True
        return []

    monkeypatch.setattr(usb_gui, "_run_ble_operation", fake_run_ble_operation)
    monkeypatch.setattr(usb_gui.asyncio, "run", fake_asyncio_run)

    assert usb_gui.can_scan_bluetooth_devices() is True
    assert calls == {"wrapped": True, "run_called": True}


def test_can_scan_bluetooth_devices_returns_false_on_probe_exception(monkeypatch) -> None:
    monkeypatch.setattr(usb_gui, "is_ble_available", lambda: True)

    def raise_runtime_error(_operation):
        raise RuntimeError("probe failed")

    monkeypatch.setattr(usb_gui, "_run_ble_operation", raise_runtime_error)

    assert usb_gui.can_scan_bluetooth_devices() is False


def test_get_bluetooth_devices_retries_support_probe_on_macos(monkeypatch) -> None:
    gui = USBGui(network=object(), loop_in_thread=object())
    probe_calls: list[bool] = []

    def fake_probe() -> bool:
        probe_calls.append(True)
        return len(probe_calls) > 1

    monkeypatch.setattr(usb_gui.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(usb_gui, "can_scan_bluetooth_devices", fake_probe)
    monkeypatch.setattr(usb_gui, "_run_ble_operation", lambda operation: operation())
    monkeypatch.setattr(gui, "_discover_bluetooth_devices", lambda: [{"transport": "bluetooth"}])

    assert gui.get_bluetooth_devices() == [{"transport": "bluetooth"}]
    assert len(probe_calls) == 2
    assert gui._bluetooth_scan_supported is True


def test_get_device_exposes_bluetooth_scan_callback_when_enabled(monkeypatch) -> None:
    gui = USBGui(network=object(), loop_in_thread=object(), enable_bluetooth=True)
    captured: dict[str, object] = {}
    callback = lambda: []
    monkeypatch.setattr(gui, "get_bluetooth_devices", callback)

    class _FakeDialog:
        def __init__(
            self,
            parent,
            network,
            usb_scan_callback,
            bluetooth_scan_callback,
            install_udev_callback,
            autoselect_if_1_device,
        ):
            _ = parent
            _ = network
            _ = usb_scan_callback
            _ = install_udev_callback
            _ = autoselect_if_1_device
            captured["bluetooth_scan_callback"] = bluetooth_scan_callback

        def exec(self) -> bool:
            return False

        def get_selected_device(self):
            raise AssertionError("Not expected when dialog is rejected")

    monkeypatch.setattr(usb_gui, "DeviceDialog", _FakeDialog)

    assert gui.get_device() is None
    assert captured["bluetooth_scan_callback"] is callback


def test_get_device_hides_bluetooth_scan_callback_when_disabled(monkeypatch) -> None:
    gui = USBGui(network=object(), loop_in_thread=object(), enable_bluetooth=False)
    captured: dict[str, object] = {}

    class _FakeDialog:
        def __init__(
            self,
            parent,
            network,
            usb_scan_callback,
            bluetooth_scan_callback,
            install_udev_callback,
            autoselect_if_1_device,
        ):
            _ = parent
            _ = network
            _ = usb_scan_callback
            _ = install_udev_callback
            _ = autoselect_if_1_device
            captured["bluetooth_scan_callback"] = bluetooth_scan_callback

        def exec(self) -> bool:
            return False

        def get_selected_device(self):
            raise AssertionError("Not expected when dialog is rejected")

    monkeypatch.setattr(usb_gui, "DeviceDialog", _FakeDialog)

    assert gui.get_device() is None
    assert captured["bluetooth_scan_callback"] is None
