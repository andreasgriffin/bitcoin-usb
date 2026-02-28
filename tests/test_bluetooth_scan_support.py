from bitcoin_usb import usb_gui


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
