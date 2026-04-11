from types import SimpleNamespace

from bitcoin_usb.dialogs import DeviceDialog


class _FakeButton:
    def __init__(self) -> None:
        self.default = False
        self.focused = False

    def setDefault(self, value: bool) -> None:
        self.default = value

    def setFocus(self) -> None:
        self.focused = True


class _FakeItem:
    def __init__(self, widget) -> None:
        self._widget = widget

    def widget(self):
        return self._widget


class _FakeLayout:
    def __init__(self, widgets: list[object]) -> None:
        self._widgets = widgets

    def count(self) -> int:
        return len(self._widgets)

    def itemAt(self, index: int) -> _FakeItem:
        return _FakeItem(self._widgets[index])


def test_on_scan_finished_defaults_to_first_device_button(monkeypatch) -> None:
    monkeypatch.setattr("bitcoin_usb.dialogs.QPushButton", _FakeButton)
    usb_scan_button = _FakeButton()
    device_button = _FakeButton()
    dialog = SimpleNamespace(
        _devices_by_key={("trezor", "usb:1", "usb"): {"type": "trezor"}},
        devices_layout=_FakeLayout([device_button]),
        usb_scan_button=usb_scan_button,
        bluetooth_scan_button=_FakeButton(),
        install_udev_button=_FakeButton(),
        cancel_button=_FakeButton(),
        _scan_finished_message="",
        _set_scanning=lambda scanning: None,
        _set_instructions_message=lambda message: None,
        _stop_scan=lambda wait_timeout_ms: None,
    )
    dialog._set_default_action_button = lambda button: DeviceDialog._set_default_action_button(dialog, button)  # type:  ignore

    DeviceDialog._on_scan_finished(dialog)  # type:  ignore

    assert device_button.default is True
    assert device_button.focused is True
    assert usb_scan_button.default is False


def test_on_scan_finished_defaults_to_usb_scan_button_when_empty(monkeypatch) -> None:
    monkeypatch.setattr("bitcoin_usb.dialogs.QPushButton", _FakeButton)
    usb_scan_button = _FakeButton()
    dialog = SimpleNamespace(
        _devices_by_key={},
        devices_layout=_FakeLayout([]),
        usb_scan_button=usb_scan_button,
        bluetooth_scan_button=_FakeButton(),
        install_udev_button=_FakeButton(),
        cancel_button=_FakeButton(),
        _scan_finished_message="",
        _set_scanning=lambda scanning: None,
        _set_instructions_message=lambda message: None,
        _stop_scan=lambda wait_timeout_ms: None,
    )
    dialog._set_default_action_button = lambda button: DeviceDialog._set_default_action_button(dialog, button)  # type:  ignore

    DeviceDialog._on_scan_finished(dialog)  # type:  ignore

    assert usb_scan_button.default is True
    assert usb_scan_button.focused is True


def test_on_scan_result_refreshes_dialog_size() -> None:
    calls: list[str] = []
    devices_by_key: dict[tuple[str, str, str], dict[str, str]] = {}

    def replace_devices(transport: str, devices: list[dict[str, str]]) -> None:
        calls.append(f"replace:{transport}:{len(devices)}")
        devices_by_key.clear()
        for device in devices:
            devices_by_key[(device["type"], device["path"], device["transport"])] = device

    dialog = SimpleNamespace(
        _devices_by_key=devices_by_key,
        _has_completed_usb_scan=False,
        _replace_devices_for_transport=replace_devices,
        _update_install_udev_button_visibility=lambda: calls.append("udev"),
        _render_devices=lambda: calls.append("render"),
        _refresh_dialog_size=lambda: calls.append("resize"),
        _on_scan_finished=lambda: calls.append("finished"),
        autoselect_if_1_device=False,
    )

    DeviceDialog._on_scan_result(
        dialog,  # type:  ignore
        "bluetooth",
        [{"type": "trezor", "path": "ble:1", "transport": "bluetooth"}],
    )

    assert calls == ["replace:bluetooth:1", "render", "resize", "finished"]
