import sys
from collections.abc import Callable
from functools import partial
from typing import Any

import bdkpython as bdk
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QGuiApplication, QIcon, QShowEvent
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from bitcoin_usb.util import get_icon_path


def get_message_box(
    text: str, icon: QMessageBox.Icon = QMessageBox.Icon.Information, title: str = ""
) -> QMessageBox:
    # Create the text box
    msg_box = QMessageBox()
    msg_box.setIcon(icon)
    msg_box.setText(text)
    msg_box.setWindowTitle(title)

    # Add standard buttons
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)

    return msg_box


# Worker class for the blocking operation
class Worker(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(Exception)  # New signal for errors

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            func_result = self.func(*self.args, **self.kwargs)
            self.finished.emit(func_result)  # Emit the func_result if successful
        except Exception as e:
            self.error.emit(e)  # Emit error if an exception occurs


class DeviceDialog(QDialog):
    _detached_scan_threads: set[QThread] = set()
    _usb_icon_path = get_icon_path("bi--usb-symbol.svg")
    _bluetooth_icon_path = get_icon_path("bi--bluetooth.svg")

    def __init__(
        self,
        parent,
        network: bdk.Network,
        usb_scan_callback: Callable[[], list[dict[str, Any]]],
        bluetooth_scan_callback: Callable[[], list[dict[str, Any]]] | None = None,
        install_udev_callback: Callable[[], None] | None = None,
        autoselect_if_1_device: bool = False,
    ):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Select the detected device"))
        self._layout = QVBoxLayout(self)
        self.setModal(True)

        self.network = network
        self.usb_scan_callback = usb_scan_callback
        self.bluetooth_scan_callback = bluetooth_scan_callback
        self.install_udev_callback = install_udev_callback
        self.autoselect_if_1_device = autoselect_if_1_device
        self.selected_device: dict[str, Any] | None = None
        self._devices_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._scan_thread: QThread | None = None
        self._scan_worker: Worker | None = None
        self._has_auto_scanned_on_open = False
        self._has_completed_usb_scan = False
        self._scan_finished_message = ""
        self.usb_icon = self._load_icon(self._usb_icon_path)
        self.bluetooth_icon = self._load_icon(self._bluetooth_icon_path)

        self.instructions_label = QLabel(self)
        self.instructions_label.setWordWrap(True)
        self.instructions_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._set_instructions_message("")
        self._layout.addWidget(self.instructions_label)

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)  # indeterminate spinner
        self.progress.hide()
        self._layout.addWidget(self.progress)

        self.devices_group = QGroupBox(self.tr("Detected devices"), self)
        self.devices_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.devices_layout = QVBoxLayout(self.devices_group)
        self._layout.addWidget(self.devices_group, stretch=1)

        self.actions_bar = QDialogButtonBox(self)
        self.usb_scan_button = self.actions_bar.addButton(
            self.tr("Scan USB devices"), QDialogButtonBox.ButtonRole.ActionRole
        )
        self.usb_scan_button.setIcon(self.usb_icon)
        self.usb_scan_button.clicked.connect(self.scan_usb_devices)
        self.usb_scan_button.setAutoDefault(True)
        self.usb_scan_button.setDefault(True)

        self.bluetooth_scan_button: QPushButton | None = None
        if self.bluetooth_scan_callback:
            self.bluetooth_scan_button = self.actions_bar.addButton(
                self.tr("Scan Bluetooth devices"), QDialogButtonBox.ButtonRole.ActionRole
            )
            self.bluetooth_scan_button.setIcon(self.bluetooth_icon)
            self.bluetooth_scan_button.clicked.connect(self.scan_for_bluetooth_devices)
            self.bluetooth_scan_button.setAutoDefault(False)

        self.install_udev_button: QPushButton | None = None
        if self.install_udev_callback and sys.platform.startswith("linux"):
            self.install_udev_button = self.actions_bar.addButton(
                self.tr("Install udev rules"), QDialogButtonBox.ButtonRole.ActionRole
            )
            self.install_udev_button.clicked.connect(self.install_udev_callback)
            self.install_udev_button.setAutoDefault(False)
            self.install_udev_button.setVisible(False)

        self.cancel_button = self.actions_bar.addButton(QDialogButtonBox.StandardButton.Cancel)
        self.actions_bar.rejected.connect(self.reject)
        self.cancel_button.setAutoDefault(False)
        self._layout.addWidget(self.actions_bar)

        # ensure the dialog has its “natural” size
        self.adjustSize()
        # get screen center
        if primaryScreen := QGuiApplication.primaryScreen():
            screen_geom = primaryScreen.availableGeometry()
            screen_center = screen_geom.center()

            # move this dialog’s frame so that its center is at screen_center
            fg = self.frameGeometry()
            fg.moveCenter(screen_center)
            self.move(fg.topLeft())

        # Scan starts automatically when the dialog is shown.

    def select_device(self, device: dict[str, Any]):
        self.selected_device = device
        self.accept()

    @staticmethod
    def _load_icon(icon_path: str) -> QIcon:
        return QIcon(icon_path)

    def _transport_icon(self, transport: str) -> QIcon:
        if transport == "bluetooth":
            return self.bluetooth_icon
        return self.usb_icon

    def _button_text(self, device: dict[str, Any]) -> str:
        device_type = str(device.get("type", "")).strip()
        model = str(device.get("model", "")).strip()

        label = device_type
        if model and model != device_type:
            label = f"{device_type} - {model}"

        if device.get("transport") != "bluetooth":
            return label

        details: list[str] = []
        if bluetooth_name := str(device.get("bluetooth_name", "")).strip():
            details.append(bluetooth_name)
        if bluetooth_serial := str(device.get("bluetooth_serial_number", "")).strip():
            details.append(self.tr("SN {serial}").format(serial=bluetooth_serial))
        if bluetooth_address := str(device.get("bluetooth_address", "")).strip():
            details.append(bluetooth_address)

        details_text = f" - {details[0]}" if details else ""
        return f"{label} (Bluetooth){details_text}"

    def _device_key(self, device: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(device.get("type", "")),
            str(device.get("path", "")),
            str(device.get("transport", "usb")),
        )

    def _set_scanning(self, scanning: bool):
        self.progress.setVisible(scanning)
        self.usb_scan_button.setEnabled(not scanning)
        if self.bluetooth_scan_button:
            self.bluetooth_scan_button.setEnabled(not scanning)
        if self.install_udev_button:
            if scanning:
                self.install_udev_button.setVisible(False)
            else:
                self._update_install_udev_button_visibility()

    def _instructions_base_text(self) -> str:
        return self.tr(
            "1. Connect your hardware signer\n2. Click Scan\n3. Unlock the device\n4. Select the device"
        )

    def _set_instructions_message(self, hint: str) -> None:
        text = self._instructions_base_text()
        if hint:
            text = f"{text}\n\n{hint}"
        self.instructions_label.setText(text)

    def _render_devices(self):
        while self.devices_layout.count():
            item = self.devices_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.setHidden(True)
                widget.setParent(None)

        devices = list(self._devices_by_key.values())
        devices.sort(
            key=lambda d: (
                str(d.get("transport", "usb")),
                str(d.get("type", "")),
                str(d.get("model", "")),
                str(d.get("bluetooth_name", "")),
                str(d.get("bluetooth_address", "")),
                str(d.get("path", "")),
            )
        )
        if not devices:
            empty_label = QLabel(self.tr("No devices found"), self.devices_group)
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.devices_layout.addWidget(empty_label)
            return

        for device in devices:
            button = QPushButton(self._button_text(device), self)
            button.setIcon(self._transport_icon(str(device.get("transport", "usb"))))
            button.clicked.connect(partial(self.select_device, device))
            button.setAutoDefault(False)
            self.devices_layout.addWidget(button)

    def _replace_devices_for_transport(self, transport: str, devices: list[dict[str, Any]]) -> None:
        self._devices_by_key = {
            k: v for k, v in self._devices_by_key.items() if str(v.get("transport", "usb")) != transport
        }
        for device in devices:
            normalized = dict(device)
            normalized["transport"] = str(normalized.get("transport", transport))
            self._devices_by_key[self._device_key(normalized)] = normalized

    def _usb_device_count(self) -> int:
        return sum(
            1 for device in self._devices_by_key.values() if str(device.get("transport", "usb")) == "usb"
        )

    def _update_install_udev_button_visibility(self) -> None:
        if not self.install_udev_button:
            return
        show_button = self._has_completed_usb_scan and self._usb_device_count() == 0
        self.install_udev_button.setVisible(show_button)

    def _empty_state_hint_text(self) -> str:
        options = [self.tr("scan USB devices")]
        if self.bluetooth_scan_callback:
            options.append(self.tr("scan Bluetooth devices"))
        if self.install_udev_button and self.install_udev_button.isVisible():
            options.append(self.tr("install udev rules"))

        if len(options) == 1:
            action_text = options[0]
        elif len(options) == 2:
            action_text = f"{options[0]} {self.tr('or')} {options[1]}"
        else:
            action_text = ", ".join(options[:-1]) + f", {self.tr('or')} {options[-1]}"

        return self.tr("Try to {actions}.").format(actions=action_text)

    def _on_scan_result(self, source: str, result: object):
        devices = result if isinstance(result, list) else []
        transport = "bluetooth" if source == "bluetooth" else "usb"
        self._replace_devices_for_transport(transport=transport, devices=devices)
        if transport == "usb":
            self._has_completed_usb_scan = True
            self._update_install_udev_button_visibility()
        self._render_devices()

        total = len(self._devices_by_key)
        if total and self.autoselect_if_1_device and total == 1:
            self._on_scan_finished()
            self.selected_device = next(iter(self._devices_by_key.values()))
            self.accept()
            return

        self._on_scan_finished()

    def _on_scan_error(self, source: str, exception: Exception):
        if source == "usb":
            self._has_completed_usb_scan = True
            self._update_install_udev_button_visibility()
        get_message_box(
            text=self.tr("Device scan failed: {error}").format(error=str(exception)),
            title=self.tr("Device scan"),
            icon=QMessageBox.Icon.Critical,
        ).exec()
        self._on_scan_finished()

    def _on_scan_finished(self):
        self._set_scanning(False)
        self._set_instructions_message(self._scan_finished_message)
        self._scan_finished_message = ""
        self.usb_scan_button.setDefault(True)
        self.usb_scan_button.setFocus()
        self._stop_scan(wait_timeout_ms=50)

    @classmethod
    def _track_detached_scan_thread(cls, thread: QThread, worker: Worker | None) -> None:
        cls._detached_scan_threads.add(thread)

        def _cleanup_detached_thread() -> None:
            if worker:
                worker.deleteLater()
            thread.deleteLater()
            cls._detached_scan_threads.discard(thread)

        thread.finished.connect(_cleanup_detached_thread)

    @staticmethod
    def _disconnect_scan_worker(worker: Worker) -> None:
        for signal in (worker.finished, worker.error):
            try:
                signal.disconnect()
            except TypeError:
                # No connections remain.
                pass

    def _stop_scan(self, wait_timeout_ms: int) -> None:
        worker = self._scan_worker
        thread = self._scan_thread
        self._scan_worker = None
        self._scan_thread = None

        if not thread:
            return

        if worker:
            self._disconnect_scan_worker(worker)

        if thread.isRunning():
            thread.requestInterruption()
            thread.quit()
            if wait_timeout_ms > 0 and thread.wait(wait_timeout_ms):
                if worker:
                    worker.deleteLater()
                thread.deleteLater()
                return
            thread.setParent(None)
            self._track_detached_scan_thread(thread=thread, worker=worker)
            return

        if worker:
            worker.deleteLater()
        thread.deleteLater()

    def _start_scan(
        self, scan_fn: Callable[[], list[dict[str, Any]]], source: str, message: str, finished_message: str
    ) -> None:
        if self._scan_thread and self._scan_thread.isRunning():
            return

        self._set_scanning(True)
        self._scan_finished_message = finished_message
        self._scan_worker = Worker(scan_fn)
        self._scan_thread = QThread(self)
        self._scan_worker.moveToThread(self._scan_thread)
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.finished.connect(lambda result: self._on_scan_result(source, result))
        self._scan_worker.error.connect(lambda exception: self._on_scan_error(source, exception))
        self._scan_thread.start()
        self._set_instructions_message(message)

    def scan_usb_devices(self):
        self._start_scan(
            scan_fn=self.usb_scan_callback,
            source="usb",
            message=self.tr("Unlock your hardware signer"),
            finished_message="",
        )

    def scan_for_bluetooth_devices(self):
        if not self.bluetooth_scan_callback:
            return
        self._start_scan(
            scan_fn=self.bluetooth_scan_callback,
            source="bluetooth",
            message=self.tr("Scanning for compatible Bluetooth hardware signers."),
            finished_message="",
        )

    def get_selected_device(self) -> dict[str, Any] | None:
        return self.selected_device

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self._stop_scan(wait_timeout_ms=0)
        super().closeEvent(a0)

    def showEvent(self, a0: QShowEvent | None) -> None:
        super().showEvent(a0)
        if not self._has_auto_scanned_on_open:
            self._has_auto_scanned_on_open = True
            self.scan_usb_devices()
