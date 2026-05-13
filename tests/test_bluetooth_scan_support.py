from typing import cast

from bitcoin_usb import usb_gui
from bitcoin_usb.dialogs import AutoScanMode, DeviceDialog
from bitcoin_usb.usb_gui import USBGui


def test_can_scan_bluetooth_devices_uses_ble_operation_wrapper(monkeypatch) -> None:
    calls: dict[str, object] = {"run_called": False}

    monkeypatch.setattr(usb_gui, "is_ble_available", lambda: True)
    loop_in_thread = object()

    def fake_scan_ble_devices(loop, scan_timeout):
        calls["run_called"] = True
        calls["loop"] = loop
        calls["scan_timeout"] = scan_timeout
        return []

    monkeypatch.setattr(usb_gui, "scan_ble_devices", fake_scan_ble_devices)

    assert usb_gui.can_scan_bluetooth_devices(loop_in_thread) is True
    assert calls == {
        "run_called": True,
        "loop": loop_in_thread,
        "scan_timeout": 0.2,
    }


def test_can_scan_bluetooth_devices_returns_false_on_probe_exception(monkeypatch) -> None:
    monkeypatch.setattr(usb_gui, "is_ble_available", lambda: True)

    def fail_scan_ble_devices(_loop_in_thread, _scan_timeout):
        raise RuntimeError("probe failed")

    monkeypatch.setattr(usb_gui, "scan_ble_devices", fail_scan_ble_devices)

    loop_in_thread = object()
    assert usb_gui.can_scan_bluetooth_devices(loop_in_thread=loop_in_thread) is False


def test_get_bluetooth_devices_retries_support_probe_on_macos(monkeypatch) -> None:
    gui = USBGui(network=object(), loop_in_thread=object())
    probe_calls: list[object] = []

    def fake_probe(loop_in_thread, probe_timeout: float = 0.2) -> bool:
        probe_calls.append(loop_in_thread)
        return len(probe_calls) > 1

    monkeypatch.setattr(usb_gui.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(usb_gui, "can_scan_bluetooth_devices", fake_probe)
    monkeypatch.setattr(gui, "_discover_bluetooth_devices", lambda: [{"transport": "bluetooth"}])

    assert gui.get_bluetooth_devices() == [{"transport": "bluetooth"}]
    assert len(probe_calls) == 2
    assert probe_calls == [gui.loop_in_thread, gui.loop_in_thread]
    assert gui._bluetooth_scan_supported is True


def test_get_device_exposes_bluetooth_scan_callback_when_enabled(monkeypatch) -> None:
    gui = USBGui(
        network=object(),
        loop_in_thread=object(),
        enable_bluetooth=True,
        autoscan_mode=AutoScanMode.BLUETOOTH,
    )
    captured: dict[str, object] = {}
    callback = lambda: []  # type: ignore
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
            autoscan_mode,
        ):
            _ = parent
            _ = network
            _ = usb_scan_callback
            _ = install_udev_callback
            _ = autoselect_if_1_device
            captured["bluetooth_scan_callback"] = bluetooth_scan_callback
            captured["autoscan_mode"] = autoscan_mode

        def exec(self) -> bool:
            return False

        def get_selected_device(self):
            raise AssertionError("Not expected when dialog is rejected")

    monkeypatch.setattr(usb_gui, "DeviceDialog", _FakeDialog)

    assert gui.get_device() is None
    assert captured["bluetooth_scan_callback"] is callback
    assert captured["autoscan_mode"] is AutoScanMode.BLUETOOTH


def test_get_device_hides_bluetooth_scan_callback_when_disabled(monkeypatch) -> None:
    gui = USBGui(
        network=object(),
        loop_in_thread=object(),
        enable_bluetooth=False,
        autoscan_mode=AutoScanMode.BLUETOOTH,
    )
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
            autoscan_mode,
        ):
            _ = parent
            _ = network
            _ = usb_scan_callback
            _ = install_udev_callback
            _ = autoselect_if_1_device
            captured["bluetooth_scan_callback"] = bluetooth_scan_callback
            captured["autoscan_mode"] = autoscan_mode

        def exec(self) -> bool:
            return False

        def get_selected_device(self):
            raise AssertionError("Not expected when dialog is rejected")

    monkeypatch.setattr(usb_gui, "DeviceDialog", _FakeDialog)

    assert gui.get_device() is None
    assert captured["bluetooth_scan_callback"] is None
    assert captured["autoscan_mode"] is AutoScanMode.OFF


def test_set_autoscan_mode_updates_mode() -> None:
    gui = USBGui(network=object(), loop_in_thread=object())
    bluetooth_gui = USBGui(network=object(), loop_in_thread=object())

    gui.set_autoscan_mode(AutoScanMode.OFF)
    assert gui.autoscan_mode is AutoScanMode.OFF

    bluetooth_gui.set_autoscan_mode(AutoScanMode.BLUETOOTH)
    assert bluetooth_gui.autoscan_mode is AutoScanMode.BLUETOOTH


def test_autoscan_mode_rejects_invalid_value() -> None:
    try:
        AutoScanMode("wifi")
    except ValueError as exc:
        assert "wifi" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid autoscan mode")


def test_device_dialog_runs_requested_initial_autoscan() -> None:
    calls: list[str] = []

    class _StubDialog:
        def __init__(self, autoscan_mode: AutoScanMode) -> None:
            self.autoscan_mode = autoscan_mode
            self.bluetooth_scan_callback = object()

        def scan_usb_devices(self) -> None:
            calls.append("usb")

        def scan_for_bluetooth_devices(self) -> None:
            calls.append("bluetooth")

    DeviceDialog._run_initial_autoscan(cast(DeviceDialog, _StubDialog(AutoScanMode.OFF)))
    DeviceDialog._run_initial_autoscan(cast(DeviceDialog, _StubDialog(AutoScanMode.USB)))
    DeviceDialog._run_initial_autoscan(cast(DeviceDialog, _StubDialog(AutoScanMode.BLUETOOTH)))

    assert calls == ["usb", "bluetooth"]
