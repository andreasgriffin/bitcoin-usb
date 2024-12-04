import logging
import platform
import re
from typing import Any, Dict, List, Optional, Tuple

import bdkpython as bdk
import hwilib.commands as hwi_commands
from hwilib.devices.bitbox02 import Bitbox02Client
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QPushButton

from bitcoin_usb.address_types import AddressType
from bitcoin_usb.dialogs import DeviceDialog, ThreadedWaitingDialog, get_message_box
from bitcoin_usb.hwi_quick import HWIQuick

from .device import USBDevice
from .i18n import translate

logger = logging.getLogger(__name__)


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
    signal_end_hwi_blocker = pyqtSignal()

    def __init__(
        self,
        network: bdk.Network,
        allow_emulators_only_for_testnet_works: bool = True,
        autoselect_if_1_device=False,
        initalization_label="",
        parent=None,
    ) -> None:
        super().__init__()
        self.autoselect_if_1_device = autoselect_if_1_device
        self.network = network
        self._parent = parent
        self.initalization_label = clean_string(initalization_label)
        self.allow_emulators_only_for_testnet_works = allow_emulators_only_for_testnet_works

    def set_initalization_label(self, value: str):
        self.initalization_label = clean_string(value)

    def get_devices(self, slow_hwi_listing=False) -> List[Dict[str, Any]]:
        "Returns the found devices WITHOUT unlocking them first.  Misses the fingerprints"
        allow_emulators = False
        devices = []

        try:
            if slow_hwi_listing:
                allow_emulators = True
                if self.allow_emulators_only_for_testnet_works:
                    allow_emulators = self.network in [
                        bdk.Network.REGTEST,
                        bdk.Network.TESTNET,
                        bdk.Network.SIGNET,
                    ]

                devices = ThreadedWaitingDialog(
                    func=lambda: hwi_commands.enumerate(allow_emulators=allow_emulators),
                    title=self.tr("Unlock USB devices"),
                    message=self.tr("Please unlock USB devices"),
                ).get_result()
            else:
                devices = HWIQuick(network=self.network).enumerate()

        except Exception as e:
            logger.error(str(e))
        return devices

    def get_device(self, slow_hwi_listing=False) -> Dict[str, Any] | None:
        "Returns the found devices WITHOUT unlocking them first.  Misses the fingerprints"
        devices = self.get_devices(slow_hwi_listing=slow_hwi_listing)

        if not devices:
            get_message_box(
                translate("bitcoin_usb", "No USB devices found"),
                title=translate("bitcoin_usb", "USB Devices"),
            ).exec()
            self.signal_end_hwi_blocker.emit()
            return None
        if len(devices) == 1 and self.autoselect_if_1_device:
            return devices[0]
        else:
            dialog = DeviceDialog(self._parent, devices, self.network)
            if dialog.exec():
                return dialog.get_selected_device()
            else:
                get_message_box(
                    translate("bitcoin_usb", "No device selected"),
                    title=translate("bitcoin_usb", "USB Devices"),
                ).exec()
                self.signal_end_hwi_blocker.emit()
        return None

    def sign(self, psbt: bdk.PartiallySignedTransaction) -> Optional[bdk.PartiallySignedTransaction]:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:

            with USBDevice(
                selected_device=selected_device,
                network=self.network,
                initalization_label=self.initalization_label,
            ) as dev:
                return dev.sign_psbt(psbt)
        except Exception as e:
            if not self.handle_exception_sign(e):
                raise
        finally:
            self.signal_end_hwi_blocker.emit()

        return None

    def get_fingerprint_and_xpubs(self) -> Optional[Tuple[Dict[str, Any], str, Dict[AddressType, str]]]:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:
            with USBDevice(
                selected_device=selected_device,
                network=self.network,
                initalization_label=self.initalization_label,
            ) as dev:
                return selected_device, dev.get_fingerprint(), dev.get_xpubs()
        except Exception as e:
            if not self.handle_exception_get_fingerprint_and_xpubs(e):
                raise
        finally:
            self.signal_end_hwi_blocker.emit()
        return None

    def get_fingerprint_and_xpub(self, key_origin: str) -> Optional[Tuple[Dict[str, Any], str, str]]:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:
            with USBDevice(
                selected_device=selected_device,
                network=self.network,
                initalization_label=self.initalization_label,
            ) as dev:
                return selected_device, dev.get_fingerprint(), dev.get_xpub(key_origin)
        except Exception as e:
            if not self.handle_exception_get_fingerprint_and_xpubs(e):
                raise
        finally:
            self.signal_end_hwi_blocker.emit()
        return None

    def sign_message(self, message: str, bip32_path: str) -> Optional[str]:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:
            with USBDevice(
                selected_device=selected_device,
                network=self.network,
                initalization_label=self.initalization_label,
            ) as dev:
                return dev.sign_message(message, bip32_path)
        except Exception as e:
            if not self.handle_exception_sign_message(e):
                raise
        finally:
            self.signal_end_hwi_blocker.emit()
        return None

    def display_address(
        self,
        address_descriptor: str,
    ) -> Optional[str]:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:
            with USBDevice(
                selected_device=selected_device,
                network=self.network,
                initalization_label=self.initalization_label,
            ) as dev:
                return dev.display_address(
                    address_descriptor=address_descriptor,
                )
        except Exception as e:
            if not self.handle_exception_display_address(e):
                raise
        finally:
            self.signal_end_hwi_blocker.emit()
        return None

    def wipe_device(
        self,
    ) -> Optional[bool]:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:
            with USBDevice(
                selected_device=selected_device,
                network=self.network,
                initalization_label=self.initalization_label,
            ) as dev:
                return dev.wipe_device()
        except Exception as e:
            if not self.handle_exception_wipe(e):
                raise
        finally:
            self.signal_end_hwi_blocker.emit()
        return None

    def write_down_seed(
        self,
    ) -> Optional[bool]:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:
            with USBDevice(
                selected_device=selected_device,
                network=self.network,
                initalization_label=self.initalization_label,
            ) as dev:
                if isinstance(dev.client, Bitbox02Client):
                    return dev.write_down_seed(dev.client)
                else:
                    QMessageBox.information(
                        None, "Not supported", "This is currently only supported for Bitbox02"
                    )
        except Exception as e:
            if not self.handle_exception_write_down_seed(e):
                raise
        finally:
            self.signal_end_hwi_blocker.emit()
        return None

    def register_multisig(
        self,
        address_descriptor: str,
    ) -> Optional[str]:
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
            with USBDevice(
                selected_device=selected_device,
                network=self.network,
                initalization_label=self.initalization_label,
            ) as dev:
                return dev.display_address(
                    address_descriptor=address_descriptor,
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

        os_name = platform.system()

        if os_name == "Linux":
            self.show_error_message_linux(text)
        else:
            self.show_error_message(text)

    def show_error_message_linux(self, text: str) -> None:
        # Create the text box
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setText(text)
        msg_box.setWindowTitle(translate("bitcoin_usb", "Error"))

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
            install_button.clicked.connect(lambda: self.linux_cmd_install_udev_as_sudo())

        # Show the text box and wait for a response
        msg_box.exec()

    def linux_cmd_install_udev_as_sudo(self) -> None:
        from bitcoin_usb.udevwrapper import UDevWrapper

        UDevWrapper().linux_cmd_install_udev_as_sudo()
        get_message_box(
            translate("bitcoin_usb", "Please restart your computer for the changes to take effect."),
            QMessageBox.Icon.Information,
            translate("bitcoin_usb", "Restart computer"),
        ).exec()
