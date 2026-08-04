import threading
import time
from concurrent.futures import Future
from types import SimpleNamespace

from PyQt6.QtCore import QCoreApplication

from bitcoin_usb import dialogs
from bitcoin_usb.device import DialogNoiseConfig, ThreadedCapturePrintDialogBitBox02
from bitcoin_usb.dialogs import DeviceDialog


class _FakeButton:
    def __init__(self) -> None:
        self.default = False
        self.focused = False
        self.visible = False

    def setDefault(self, value: bool) -> None:
        self.default = value

    def setFocus(self) -> None:
        self.focused = True

    def setVisible(self, value: bool) -> None:
        self.visible = value


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


def test_load_icon_uses_theme_aware_svg_tools(monkeypatch) -> None:
    expected_icon = object()
    monkeypatch.setattr(dialogs.svg_tools, "get_QIcon", lambda icon_name: expected_icon)

    icon = DeviceDialog._load_icon("bi--usb-symbol.svg")

    assert icon is expected_icon


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
        _active_scan_future=None,
        _set_scanning=lambda scanning: None,
        _set_instructions_message=lambda message: None,
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
        _active_scan_future=None,
        _set_scanning=lambda scanning: None,
        _set_instructions_message=lambda message: None,
        _default_scan_button=lambda: usb_scan_button,
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
        _active_scan_token=1,
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
        1,
        [{"type": "trezor", "path": "ble:1", "transport": "bluetooth"}],
    )

    assert calls == ["replace:bluetooth:1", "render", "resize", "finished"]


def test_start_scan_uses_loop_in_thread_callbacks() -> None:
    calls: list[str] = []

    class _FakeLoop:
        def run_task(self, coro, on_success=None, on_error=None):
            coro.close()
            calls.append("run_task")
            if on_success is not None:
                on_success([{"type": "trezor", "path": "usb:1"}])
            future: Future[list[dict[str, str]]] = Future()
            future.set_result([{"type": "trezor", "path": "usb:1"}])
            return future

    dialog = SimpleNamespace(
        loop_in_thread=_FakeLoop(),
        _active_scan_future=None,
        _active_scan_token=0,
        _set_scanning=lambda scanning: calls.append(f"scanning:{scanning}"),
        _set_instructions_message=lambda message: calls.append(f"message:{message}"),
        _scan_finished_message="",
        _on_scan_result=lambda source, token, result: calls.append(f"result:{source}:{token}:{len(result)}"),
        _on_scan_error=lambda source, token, exception: calls.append(f"error:{source}:{token}:{exception}"),
    )

    DeviceDialog._start_scan(
        dialog,  # type: ignore[arg-type]
        scan_fn=lambda: [{"type": "trezor", "path": "usb:1"}],
        source="usb",
        message="scan",
        finished_message="done",
    )

    assert calls == ["scanning:True", "run_task", "result:usb:1:1", "message:scan"]
    assert dialog._scan_finished_message == "done"


def test_stop_scan_cancels_active_future_and_invalidates_token() -> None:
    future: Future[object] = Future()
    dialog = SimpleNamespace(
        _active_scan_future=future,
        _active_scan_token=5,
    )

    DeviceDialog._stop_scan(dialog)  # type: ignore[arg-type]

    assert future.cancelled() is True
    assert dialog._active_scan_future is None
    assert dialog._active_scan_token == 6


def test_scan_callbacks_ignore_stale_tokens() -> None:
    calls: list[str] = []
    dialog = SimpleNamespace(
        _active_scan_token=2,
        _devices_by_key={},
        _has_completed_usb_scan=False,
        _replace_devices_for_transport=lambda transport, devices: calls.append(
            f"replace:{transport}:{len(devices)}"
        ),
        _update_install_udev_button_visibility=lambda: calls.append("udev"),
        _render_devices=lambda: calls.append("render"),
        _refresh_dialog_size=lambda: calls.append("resize"),
        _on_scan_finished=lambda: calls.append("finished"),
        autoselect_if_1_device=False,
    )

    DeviceDialog._on_scan_result(dialog, "usb", 1, [{"type": "trezor", "path": "usb:1"}])  # type: ignore[arg-type]
    DeviceDialog._on_scan_error(dialog, "usb", 1, RuntimeError("boom"))  # type: ignore[arg-type]

    assert calls == []


def test_install_udev_button_is_only_visible_on_linux(monkeypatch) -> None:
    button = _FakeButton()
    dialog = SimpleNamespace(
        install_udev_button=button,
        install_udev_callback=lambda: None,
        _has_completed_usb_scan=True,
        _usb_device_count=lambda: 0,
    )

    monkeypatch.setattr(dialogs.sys, "platform", "darwin")
    DeviceDialog._update_install_udev_button_visibility(dialog)  # type: ignore[arg-type]

    assert button.visible is False

    monkeypatch.setattr(dialogs.sys, "platform", "linux")
    DeviceDialog._update_install_udev_button_visibility(dialog)  # type: ignore[arg-type]

    assert button.visible is True


def test_threaded_capture_print_dialog_run_func_emits_result() -> None:
    captured: list[object] = []

    class _Signal:
        def emit(self, value: object) -> None:
            captured.append(value)

    dialog = SimpleNamespace(
        _func=lambda: True,
        _args=(),
        _kwargs={},
        _bridge=SimpleNamespace(finished=_Signal(), error=_Signal()),
    )

    ThreadedCapturePrintDialogBitBox02._run_func(dialog)  # type: ignore[arg-type]

    assert captured == [True]


def test_threaded_capture_print_dialog_run_func_emits_error() -> None:
    captured: list[object] = []

    class _Signal:
        def emit(self, value: object) -> None:
            captured.append(value)

    dialog = SimpleNamespace(
        _func=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        _args=(),
        _kwargs={},
        _bridge=SimpleNamespace(finished=_Signal(), error=_Signal()),
    )

    ThreadedCapturePrintDialogBitBox02._run_func(dialog)  # type: ignore[arg-type]

    assert len(captured) == 1
    assert isinstance(captured[0], RuntimeError)
    assert str(captured[0]) == "boom"


def test_threaded_capture_print_dialog_handle_error_closes_dialog() -> None:
    calls: list[str] = []

    class _Loop:
        def __init__(self, running: bool) -> None:
            self._running = running

        def isRunning(self) -> bool:
            return self._running

        def exit(self, code: int | None = None) -> None:
            calls.append(f"exit:{code}")

    dialog = SimpleNamespace(
        _worker_error=None,
        loop=_Loop(True),
        dialog_loop=_Loop(True),
        close=lambda: calls.append("close"),
    )

    ThreadedCapturePrintDialogBitBox02.handle_func_error(dialog, RuntimeError("boom"))  # type: ignore[arg-type]

    assert isinstance(dialog._worker_error, RuntimeError)
    assert calls == ["exit:None", "exit:0", "close"]


def test_bitbox02_pairing_requests_use_main_thread(monkeypatch) -> None:
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])

    main_thread_ident = threading.get_ident()
    captured: dict[str, object] = {}
    result: dict[str, bool] = {}
    errors: list[Exception] = []

    class _FakeDialog:
        def __init__(self, func, title="Processing...", message="", *args, **kwargs) -> None:
            _ = args
            _ = kwargs
            _ = message
            captured["thread_ident"] = threading.get_ident()
            captured["title"] = title
            self._func = func

        def add_text(self, text: str) -> None:
            captured["text"] = text

        def get_result(self) -> bool:
            return self._func()

    monkeypatch.setattr("bitcoin_usb.device.ThreadedCapturePrintDialogBitBox02", _FakeDialog)

    def run_request() -> None:
        try:
            result["value"] = DialogNoiseConfig().show_pairing("123456", lambda: True)
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
    assert result["value"] is True
    assert captured["thread_ident"] == main_thread_ident
    assert captured["title"] == "Pair Bitbox02"
    assert "123456" in str(captured["text"])
