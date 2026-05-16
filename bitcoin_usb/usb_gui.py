import logging
import platform
import re
import tempfile
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any, TypeVar, cast

import bdkpython as bdk
import hwilib.commands as hwi_commands
from bitcoin_safe_lib.async_tools.loop_in_thread import LoopInThread
from bitcoin_safe_lib.gui.qt.signal_tracker import SignalProtocol
from bitcoin_safe_lib.gui.qt.util import question_dialog
from bitcoin_safe_lib.util_os import xdg_open_file
from bleak import BleakClient, BleakScanner
from hwilib.devices.bitbox02 import Bitbox02Client
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMessageBox, QPushButton, QWidget

from bitcoin_usb.address_types import AddressType
from bitcoin_usb.dialogs import AutoScanMode, DeviceDialog, get_message_box
from bitcoin_usb.jade_ble_client import discover_jade_ble_devices, scan_ble_devices
from bitcoin_usb.trezor_thp import enumerate_trezor_thp_devices, is_trezor_modern_device

from .device import USBDevice, bdknetwork_to_chain
from .i18n import translate
from .util import run_device_task

logger = logging.getLogger(__name__)
MODERN_TREZOR_USE_WORKER_THREAD = True


def _merge_devices(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for device in devices:
        key = (
            str(device.get("type", "")),
            str(device.get("path", "")),
            str(device.get("transport", "usb")),
        )
        merged[key] = device
    return list(merged.values())


def enumerate_available_devices(allow_emulators: bool, chain) -> list[dict[str, Any]]:
    devices = hwi_commands.enumerate(allow_emulators=allow_emulators, chain=chain)
    return _merge_devices(devices + enumerate_trezor_thp_devices())


def is_ble_available() -> bool:
    return BleakClient is not None and BleakScanner is not None


T = TypeVar("T")


def can_scan_bluetooth_devices(loop_in_thread: LoopInThread, probe_timeout: float = 0.2) -> bool:
    if not is_ble_available():
        return False

    try:
        scan_ble_devices(loop_in_thread, scan_timeout=max(0.1, probe_timeout))
    except Exception as e:
        logger.info("Bluetooth scanning unavailable in this environment: %s", e)
        return False
    return True


def clean_string(input_string: str) -> str:
    """
    Removes special characters from a string and replaces spaces with underscores.

    Args:
    input_string (str): The string to be cleaned.

    Returns:
    str: The cleaned string.
    """
    # First, remove any character that is not a letter, number, or space
    cleaned = re.sub(r"[^\w\s]", "", input_string)

    return cleaned.replace(" ", "_")


class USBMultisigRegisteringNotSupported(Exception):
    pass


class USBGui(QObject):
    signal_end_hwi_blocker = cast(SignalProtocol[[]], pyqtSignal())

    def __init__(
        self,
        network: bdk.Network,
        loop_in_thread: LoopInThread,
        allow_emulators_only_for_testnet_works: bool = True,
        autoselect_if_1_device: bool = False,
        initalization_label: str = "",
        parent: QObject | None = None,
        enable_bluetooth: bool = True,
        autoscan_mode: AutoScanMode = AutoScanMode.USB,
        window_icon: QIcon | None = None,
    ) -> None:
        super().__init__()
        self.autoselect_if_1_device = autoselect_if_1_device
        self.network = network
        self.loop_in_thread = loop_in_thread
        self._parent = parent
        self.enable_bluetooth = enable_bluetooth
        self.autoscan_mode = autoscan_mode
        self._bluetooth_scan_supported: bool | None = None
        self.initalization_label = clean_string(initalization_label)
        self.allow_emulators_only_for_testnet_works = allow_emulators_only_for_testnet_works
        self.window_icon = window_icon

    def _apply_window_icon(self, widget: QWidget) -> None:
        if self.window_icon is not None:
            widget.setWindowIcon(self.window_icon)

    def set_initalization_label(self, value: str) -> None:
        self.initalization_label = clean_string(value)

    def set_autoscan_mode(self, autoscan_mode: AutoScanMode) -> None:
        self.autoscan_mode = autoscan_mode

    def get_devices(self) -> list[dict[str, Any]]:
        "Enumerate available HWI devices."
        allow_emulators = True
        if self.allow_emulators_only_for_testnet_works:
            allow_emulators = self.network in [
                bdk.Network.REGTEST,
                bdk.Network.TESTNET,
                bdk.Network.SIGNET,
            ]
        return enumerate_available_devices(
            allow_emulators=allow_emulators,
            chain=bdknetwork_to_chain(self.network),
        )

    def get_device(self) -> dict[str, Any] | None:
        "Returns the found devices WITHOUT unlocking them first.  Misses the fingerprints"
        bluetooth_scan_callback: Callable[[], list[dict[str, Any]]] | None = None
        if self.enable_bluetooth:
            bluetooth_scan_callback = self.get_bluetooth_devices

        dialog = DeviceDialog(
            self._parent,
            network=self.network,
            usb_scan_callback=self.get_devices,
            bluetooth_scan_callback=bluetooth_scan_callback,
            install_udev_callback=self.linux_cmd_install_udev_as_sudo
            if platform.system() == "Linux"
            else None,
            autoselect_if_1_device=self.autoselect_if_1_device,
            autoscan_mode=self._get_dialog_autoscan_mode(bluetooth_scan_callback),
            window_icon=self.window_icon,
        )
        if dialog.exec():
            return dialog.get_selected_device()
        self.signal_end_hwi_blocker.emit()
        return None

    def _get_dialog_autoscan_mode(
        self, bluetooth_scan_callback: Callable[[], list[dict[str, Any]]] | None
    ) -> AutoScanMode:
        if self.autoscan_mode is AutoScanMode.BLUETOOTH and bluetooth_scan_callback is None:
            return AutoScanMode.OFF
        return self.autoscan_mode

    def get_bluetooth_devices(self) -> list[dict[str, Any]]:
        if not self.enable_bluetooth:
            raise RuntimeError(self.tr("Bluetooth support is disabled by configuration."))
        should_retry_probe = platform.system() == "Darwin"
        if not self._is_bluetooth_scan_supported(force_refresh=should_retry_probe):
            if should_retry_probe and self._is_bluetooth_scan_supported(force_refresh=True):
                return self._discover_bluetooth_devices()
            raise RuntimeError(self.tr("Bluetooth scanning is not available in this environment."))
        return self._discover_bluetooth_devices()

    def _is_bluetooth_scan_supported(self, force_refresh: bool = False) -> bool:
        if not self.enable_bluetooth:
            return False
        if force_refresh or self._bluetooth_scan_supported is None:
            self._bluetooth_scan_supported = can_scan_bluetooth_devices(self.loop_in_thread)
        return self._bluetooth_scan_supported

    def _discover_bluetooth_devices(self) -> list[dict[str, Any]]:
        return discover_jade_ble_devices(loop_in_thread=self.loop_in_thread, scan_timeout=6.0)

    @staticmethod
    def _is_bluetooth_device(selected_device: dict[str, Any]) -> bool:
        return str(selected_device.get("transport", "")).lower() == "bluetooth"

    @staticmethod
    def _should_run_in_worker(selected_device: dict[str, Any]) -> bool:
        if is_trezor_modern_device(selected_device):
            return MODERN_TREZOR_USE_WORKER_THREAD
        if USBGui._is_bluetooth_device(selected_device):
            # Non-Trezor BLE devices must run in a worker thread (otherwise Jade breaks on Windows).
            return True
        if platform.system() == "Darwin":
            # macOS USB is kept on the caller/main thread to avoid crashes.
            return False
        # Linux/Windows USB runs in a worker thread.
        return True

    def _with_device(self, selected_device: dict[str, Any], operation: Callable[[USBDevice], T]) -> T | None:
        """
        Run one hardware-wallet operation with the required threading model.

        - macOS USB: keep calls on the caller/main thread to avoid crashes.
        - Linux/Windows USB: run calls in a worker thread.
        - Jade BLE: run calls in a worker thread, otherwise it breaks on Windows.
        - Trezor Safe 7 THP/v1: controlled by `MODERN_TREZOR_USE_WORKER_THREAD`.
        """

        def _run_operation() -> T:
            with USBDevice(
                selected_device=selected_device,
                network=self.network,
                loop_in_thread=self.loop_in_thread,
                initalization_label=self.initalization_label,
            ) as device:
                return operation(device)

        if self._should_run_in_worker(selected_device):
            return run_device_task(self.loop_in_thread, _run_operation)
        return _run_operation()

    def sign(self, psbt: bdk.Psbt) -> bdk.Psbt | None:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:
            return self._with_device(selected_device, partial(USBDevice.sign_psbt, psbt=psbt))
        except Exception as e:
            if not self.handle_exception_sign(e):
                raise
        finally:
            self.signal_end_hwi_blocker.emit()

        return None

    def get_fingerprint_and_xpubs(self) -> tuple[dict[str, Any], str, dict[AddressType, str]] | None:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:

            def _collect_xpubs(device: USBDevice) -> tuple[dict[str, Any], str, dict[AddressType, str]]:
                return (selected_device, device.get_fingerprint(), device.get_xpubs())

            return self._with_device(selected_device, _collect_xpubs)
        except Exception as e:
            if not self.handle_exception_get_fingerprint_and_xpubs(e):
                raise
        finally:
            self.signal_end_hwi_blocker.emit()
        return None

    def get_fingerprint_and_xpub(self, key_origin: str) -> tuple[dict[str, Any], str, str] | None:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:

            def _collect_xpub(device: USBDevice) -> tuple[dict[str, Any], str, str]:
                return (selected_device, device.get_fingerprint(), device.get_xpub(key_origin))

            return self._with_device(selected_device, _collect_xpub)
        except Exception as e:
            if not self.handle_exception_get_fingerprint_and_xpubs(e):
                raise
        finally:
            self.signal_end_hwi_blocker.emit()
        return None

    def sign_message(self, message: str, bip32_path: str) -> str | None:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:
            return self._with_device(
                selected_device,
                partial(USBDevice.sign_message, message=message, bip32_path=bip32_path),
            )
        except Exception as e:
            if not self.handle_exception_sign_message(e):
                raise
        finally:
            self.signal_end_hwi_blocker.emit()
        return None

    def display_address(self, address_descriptor: str) -> str | None:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:
            return self._with_device(
                selected_device,
                partial(USBDevice.display_address, address_descriptor=address_descriptor),
            )
        except Exception as e:
            if not self.handle_exception_display_address(e):
                raise
        finally:
            self.signal_end_hwi_blocker.emit()
        return None

    def wipe_device(self) -> bool | None:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:
            return self._with_device(selected_device, USBDevice.wipe_device)
        except Exception as e:
            if not self.handle_exception_wipe(e):
                raise
        finally:
            self.signal_end_hwi_blocker.emit()
        return None

    def write_down_seed(self) -> bool | None:
        selected_device = self.get_device()
        if not selected_device:
            return None
        if str(selected_device.get("type", "")).lower() != "bitbox02":
            msg_box = get_message_box(
                text="This is currently only supported for Bitbox02",
                title="Not supported",
                icon=QMessageBox.Icon.Information,
                window_icon=self.window_icon,
            )
            msg_box.exec()
            self.signal_end_hwi_blocker.emit()
            return None

        try:

            def _backup_seed(device: USBDevice) -> bool | None:
                if not isinstance(device.client, Bitbox02Client):
                    return None
                return device.write_down_seed(device.client)

            return self._with_device(selected_device, _backup_seed)
        except Exception as e:
            if not self.handle_exception_write_down_seed(e):
                raise
        finally:
            self.signal_end_hwi_blocker.emit()
        return None

    def register_multisig(self, address_descriptor: str) -> str | None:
        selected_device = self.get_device()
        if not selected_device:
            return None

        if selected_device["type"] == "coldcard":
            raise USBMultisigRegisteringNotSupported(
                self.tr(
                    "Registering multisig wallets via USB is not supported by {device_type}. Please use sd-cards or scan the QR Code."
                ).format(device_type=selected_device["type"])
            )

        try:
            return self._with_device(
                selected_device,
                partial(USBDevice.display_address, address_descriptor=address_descriptor),
            )
        except Exception as e:
            if not self.handle_exception_display_address(e):
                raise
        finally:
            self.signal_end_hwi_blocker.emit()
        return None

    def set_network(self, network: bdk.Network):
        self.network = network

    def handle_exception_get_fingerprint_and_xpubs(self, exception: Exception) -> bool:
        self.show_error_message(str(exception))
        return True

    def handle_exception_sign_message(self, exception: Exception) -> bool:
        self.show_error_message(str(exception))
        return True

    def handle_exception_display_address(self, exception: Exception) -> bool:
        self.show_error_message(str(exception))
        return True

    def handle_exception_sign(self, exception: Exception) -> bool:
        self.show_error_message(str(exception))
        return True

    def handle_exception_wipe(self, exception: Exception) -> bool:
        self.show_error_message(str(exception))
        return True

    def handle_exception_write_down_seed(self, exception: Exception) -> bool:
        self.show_error_message(str(exception))
        return True

    def show_error_message(self, text: str) -> None:
        if "temporary wallet associated with different connection" in text:
            text += "\n" + self.tr("Please try disconnecting and reconnecting the device")

        if platform.system() == "Linux":
            self.show_error_message_linux(text)
        else:
            msg_box = get_message_box(
                text=text,
                icon=QMessageBox.Icon.Critical,
                title=translate("bitcoin_usb", "Error"),
                window_icon=self.window_icon,
            )
            # Show the text box and wait for a response
            msg_box.exec()

    def show_error_message_linux(self, text: str) -> None:
        # Create the text box
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setText(text)
        msg_box.setWindowTitle(translate("bitcoin_usb", "Error"))
        self._apply_window_icon(msg_box)

        # Add standard buttons
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)

        show_udev = True
        if "cancel" in text.lower():
            show_udev = False
        if "aborted" in text.lower():
            show_udev = False
        if show_udev:
            msg_box.setInformativeText(
                translate(
                    "bitcoin_usb",
                    "USB errors can appear due to missing udev files. Do you want to install udev files now?",
                )
            )

            # Add standard buttons
            msg_box.setStandardButtons(QMessageBox.StandardButton.Cancel)

            # Add a custom button
            install_button = QPushButton(translate("bitcoin_usb", "Install udev files"))
            msg_box.addButton(install_button, QMessageBox.ButtonRole.ActionRole)
            install_button.clicked.connect(self.linux_cmd_install_udev_as_sudo)

        # Show the text box and wait for a response
        msg_box.exec()

    def linux_cmd_install_udev_as_sudo(self) -> None:
        from bitcoin_usb.udevwrapper import UDevWrapper

        UDevWrapper().linux_cmd_install_udev_as_sudo()
        res = question_dialog(
            text=self.tr(
                "Please restart your computer for the changes to take effect.",
            ),
            title=self.tr("Restart computer"),
            true_button=QMessageBox.StandardButton.Ok,
            false_button=self.tr("Manually install udev rules"),
        )
        if res is None:
            return
        elif res:
            return
        else:
            script_content = UDevWrapper()._create_udev_script()

            message = (
                self.tr("Please copy and paste the following script in a terminal to install the udev rules:")
                + "\n\n\n"
                + script_content
            )

            # Create a temporary file with a message to the user
            with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt") as temp_file:
                temp_file.write(message)
                temp_file_path = temp_file.name

            xdg_open_file(Path(temp_file_path), is_text_file=True)
