import bdkpython as bdk

from bitcoin_usb import usb_gui
from bitcoin_usb.usb_gui import USBGui


def test_get_fingerprint_and_xpubs_uses_worker_task_for_jade_ble(monkeypatch) -> None:
    gui = USBGui(network=bdk.Network.REGTEST, loop_in_thread=object())
    selected_device = {"type": "jade", "transport": "bluetooth", "path": "ble:aa"}
    calls: dict[str, object] = {"run_task": False}

    monkeypatch.setattr(gui, "get_device", lambda slow_hwi_listing=False: selected_device)

    class _FakeDevice:
        def get_fingerprint(self) -> str:
            return "f00dbabe"

        def get_xpubs(self) -> dict[str, str]:
            return {}

    class _FakeContextDevice:
        def __init__(self, *args, **kwargs):
            _ = args
            _ = kwargs

        def __enter__(self):
            return _FakeDevice()

        def __exit__(self, exc_type, exc_value, traceback):
            _ = exc_type
            _ = exc_value
            _ = traceback

    def fake_run_device_task(loop_in_thread, task):
        calls["run_task"] = True
        calls["loop"] = loop_in_thread
        return task()

    monkeypatch.setattr(usb_gui, "run_device_task", fake_run_device_task)
    monkeypatch.setattr(usb_gui, "USBDevice", _FakeContextDevice)

    result = gui.get_fingerprint_and_xpubs()

    assert result == (selected_device, "f00dbabe", {})
    assert calls == {"run_task": True, "loop": gui.loop_in_thread}


def test_get_fingerprint_and_xpubs_uses_worker_task_for_usb_on_linux(monkeypatch) -> None:
    gui = USBGui(network=bdk.Network.REGTEST, loop_in_thread=object())
    selected_device = {"type": "trezor", "path": "usb:1"}
    calls: dict[str, object] = {"run_task": False}

    def fake_get_device(slow_hwi_listing=False):
        _ = slow_hwi_listing
        return selected_device

    monkeypatch.setattr(gui, "get_device", fake_get_device)
    monkeypatch.setattr(usb_gui.platform, "system", lambda: "Linux")

    class _FakeDevice:
        def get_fingerprint(self) -> str:
            return "f00dbabe"

        def get_xpubs(self) -> dict[str, str]:
            return {}

    class _FakeContextDevice:
        def __init__(self, *args, **kwargs):
            _ = args
            _ = kwargs

        def __enter__(self):
            return _FakeDevice()

        def __exit__(self, exc_type, exc_value, traceback):
            _ = exc_type
            _ = exc_value
            _ = traceback

    def fake_run_device_task(loop_in_thread, task):
        calls["run_task"] = True
        calls["loop"] = loop_in_thread
        return task()

    monkeypatch.setattr(usb_gui, "run_device_task", fake_run_device_task)
    monkeypatch.setattr(usb_gui, "USBDevice", _FakeContextDevice)

    result = gui.get_fingerprint_and_xpubs()

    assert result == (selected_device, "f00dbabe", {})
    assert calls == {"run_task": True, "loop": gui.loop_in_thread}


def test_get_fingerprint_and_xpubs_runs_inline_for_usb_on_macos(monkeypatch) -> None:
    gui = USBGui(network=bdk.Network.REGTEST, loop_in_thread=object())
    selected_device = {"type": "trezor", "path": "usb:1"}

    def fake_get_device(slow_hwi_listing=False):
        _ = slow_hwi_listing
        return selected_device

    monkeypatch.setattr(gui, "get_device", fake_get_device)
    monkeypatch.setattr(usb_gui.platform, "system", lambda: "Darwin")

    class _FakeDevice:
        def get_fingerprint(self) -> str:
            return "f00dbabe"

        def get_xpubs(self) -> dict[str, str]:
            return {}

    class _FakeContextDevice:
        def __init__(self, *args, **kwargs):
            _ = args
            _ = kwargs

        def __enter__(self):
            return _FakeDevice()

        def __exit__(self, exc_type, exc_value, traceback):
            _ = exc_type
            _ = exc_value
            _ = traceback

    def fail_run_device_task(_loop_in_thread, _task):
        raise AssertionError("run_device_task must not be called for macOS USB")

    monkeypatch.setattr(usb_gui, "run_device_task", fail_run_device_task)
    monkeypatch.setattr(usb_gui, "USBDevice", _FakeContextDevice)

    result = gui.get_fingerprint_and_xpubs()

    assert result == (selected_device, "f00dbabe", {})
