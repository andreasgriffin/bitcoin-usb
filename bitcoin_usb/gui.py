import platform
from typing import Dict, Optional, Tuple

import bdkpython as bdk
import hwilib.commands as hwi_commands
from PyQt6.QtWidgets import QDialog, QMessageBox, QPushButton, QVBoxLayout

from bitcoin_usb.address_types import AddressType
from bitcoin_usb.udevwrapper import UDevWrapper

from .device import USBDevice, bdknetwork_to_chain
from .i18n import translate


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


class DeviceDialog(QDialog):
    def __init__(self, parent, devices, network):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Select the detected device"))
        self.layout = QVBoxLayout(self)

        # Creating a button for each device
        for device in devices:
            button = QPushButton(f"{device['type']} - {device['model']}", self)
            button.clicked.connect(lambda *args, d=device: self.select_device(d))
            self.layout.addWidget(button)

        self.selected_device = None
        self.network = network

    def select_device(self, device):
        self.selected_device = device
        self.accept()

    def get_selected_device(self):
        return self.selected_device


class USBGui:
    def __init__(
        self,
        network: bdk.Network,
        allow_emulators_only_for_testnet_works: bool = True,
        autoselect_if_1_device=False,
        parent=None,
    ) -> None:
        self.autoselect_if_1_device = autoselect_if_1_device
        self.network = network
        self.parent = parent
        self.allow_emulators_only_for_testnet_works = allow_emulators_only_for_testnet_works

    def get_device(self) -> Dict:
        allow_emulators = True
        if self.allow_emulators_only_for_testnet_works:
            allow_emulators = self.network in [bdk.Network.REGTEST, bdk.Network.TESTNET, bdk.Network.SIGNET]

        devices = hwi_commands.enumerate(
            allow_emulators=allow_emulators, chain=bdknetwork_to_chain(self.network)
        )
        if not devices:
            get_message_box(
                translate("bitcoin_usb", "No USB devices found"),
                title=translate("bitcoin_usb", "USB Devices"),
            ).exec()
            return {}
        if len(devices) == 1 and self.autoselect_if_1_device:
            return devices[0]
        else:
            dialog = DeviceDialog(self.parent, devices, self.network)
            if dialog.exec():
                return dialog.get_selected_device()
            else:
                get_message_box(
                    translate("bitcoin_usb", "No device selected"),
                    title=translate("bitcoin_usb", "USB Devices"),
                ).exec()
        return {}

    def sign(self, psbt: bdk.PartiallySignedTransaction) -> Optional[bdk.PartiallySignedTransaction]:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:
            with USBDevice(selected_device, self.network) as dev:
                return dev.sign_psbt(psbt)
        except Exception as e:
            if not self.handle_exception_sign(e):
                raise

        return None

    def get_fingerprint_and_xpubs(self) -> Optional[Tuple[str, Dict[AddressType, str]]]:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:
            with USBDevice(selected_device, self.network) as dev:
                return dev.get_fingerprint(), dev.get_xpubs()
        except Exception as e:
            if not self.handle_exception_get_fingerprint_and_xpubs(e):
                raise
        return None

    def get_fingerprint_and_xpub(self, key_origin: str) -> Optional[Tuple[str, str]]:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:
            with USBDevice(selected_device, self.network) as dev:
                return dev.get_fingerprint(), dev.get_xpub(key_origin)
        except Exception as e:
            if not self.handle_exception_get_fingerprint_and_xpubs(e):
                raise
        return None

    def sign_message(self, message: str, bip32_path: str) -> Optional[str]:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:
            with USBDevice(selected_device, self.network) as dev:
                return dev.sign_message(message, bip32_path)
        except Exception as e:
            if not self.handle_exception_sign_message(e):
                raise
        return None

    def display_address(
        self,
        address_descriptor: str,
    ) -> Optional[str]:
        selected_device = self.get_device()
        if not selected_device:
            return None

        try:
            with USBDevice(selected_device, self.network) as dev:
                return dev.display_address(
                    address_descriptor=address_descriptor,
                )
        except Exception as e:
            if not self.handle_exception_display_address(e):
                raise
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

    def show_error_message(self, text: str):

        os_name = platform.system()

        if os_name == "Linux":
            self.show_error_message_linux(text)
        else:
            self.show_error_message(text)

    def show_error_message_linux(self, text: str):
        # Create the text box
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setText(text)
        msg_box.setWindowTitle(translate("bitcoin_usb", "Error"))

        # Add standard buttons
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)

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

    def linux_cmd_install_udev_as_sudo(self):
        UDevWrapper().linux_cmd_install_udev_as_sudo()
        get_message_box(
            translate("bitcoin_usb", "Please restart your computer for the changes to take effect."),
            QMessageBox.Icon.Information,
            translate("bitcoin_usb", "Restart computer"),
        ).exec()
