from typing import Dict, Optional, Tuple

import bdkpython as bdk
import hwilib.commands as hwi_commands
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bitcoin_usb.address_types import AddressType

from .device import USBDevice


class DeviceDialog(QDialog):
    def __init__(self, parent, devices, network):
        super().__init__(parent)
        self.setWindowTitle("Select the detected device")
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


class InfoDialog(QDialog):
    def __init__(self, message, title="Info"):
        super().__init__()
        self.setWindowTitle(title)

        # Set up the dialog layout
        layout = QVBoxLayout()

        # Add a label with the information message
        message_label = QLabel(message)
        layout.addWidget(message_label)

        # Add an OK button and connect its signal
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        layout.addWidget(ok_button)

        self.setLayout(layout)


class USBGui:
    def __init__(self, network: bdk.Network, autoselect_if_1_device=False, parent=None) -> None:
        self.autoselect_if_1_device = autoselect_if_1_device
        self.network = network
        self.parent = parent

    def get_device(self) -> Dict:
        devices = hwi_commands.enumerate()
        if not devices:
            InfoDialog("No USB devices found", title="USB Devices").exec()
            return {}
        if len(devices) == 1 and self.autoselect_if_1_device:
            return devices[0]
        else:
            dialog = DeviceDialog(self.parent, devices, self.network)
            if dialog.exec():
                return dialog.get_selected_device()
            else:
                InfoDialog("No device selected", title="USB Devices").exec()
        return {}

    def sign(self, psbt: bdk.PartiallySignedTransaction) -> bdk.PartiallySignedTransaction:
        selected_device = self.get_device()
        if selected_device:
            with USBDevice(selected_device, self.network) as dev:
                return dev.sign_psbt(psbt)
        return None

    def get_fingerprint_and_xpubs(self) -> Optional[Tuple[str, Dict[AddressType, str]]]:
        selected_device = self.get_device()
        if selected_device:
            with USBDevice(selected_device, self.network) as dev:
                return dev.get_fingerprint(), dev.get_xpubs()
        return None

    def get_fingerprint_and_xpub(self, key_origin: str) -> Optional[Tuple[str, str]]:
        selected_device = self.get_device()
        if selected_device:
            with USBDevice(selected_device, self.network) as dev:
                return dev.get_fingerprint(), dev.get_xpub(key_origin)
        return None

    def sign_message(self, message: str, bip32_path: str) -> Optional[str]:
        selected_device = self.get_device()
        if selected_device:
            with USBDevice(selected_device, self.network) as dev:
                return dev.sign_message(message, bip32_path)
        return None

    def display_address(
        self,
        descriptor_str: str,
        keychain: bdk.KeychainKind,
        address_index: int,
    ):
        selected_device = self.get_device()
        if selected_device:
            with USBDevice(selected_device, self.network) as dev:
                dev.display_address(
                    descriptor_str=descriptor_str,
                    keychain=keychain,
                    address_index=address_index,
                    network=self.network,
                )


class MainWindow(QMainWindow):
    def __init__(self, network: bdk.Network):
        super().__init__()
        self.network = network
        self.usb = USBGui(network=network)

        main_widget = QWidget()
        main_widget_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        self.combo_network = QComboBox(self)
        self.combo_network.addItems([n.name for n in bdk.Network])
        self.combo_network.setCurrentText(self.network.name)
        main_widget_layout.addWidget(self.combo_network)

        # Create a tab widget and set it as the central widget
        tab_widget = QTabWidget(self)
        main_widget_layout.addWidget(tab_widget)

        # Tab 1: XPUBs
        xpubs_tab = QWidget()
        xpubs_layout = QVBoxLayout(xpubs_tab)
        self.button = QPushButton("Get xpubs", xpubs_tab)
        self.button.clicked.connect(self.on_button_clicked)
        xpubs_layout.addWidget(self.button)
        self.xpubs_text_edit = QTextEdit(xpubs_tab)
        self.xpubs_text_edit.setReadOnly(True)
        xpubs_layout.addWidget(self.xpubs_text_edit)
        tab_widget.addTab(xpubs_tab, "XPUBs")

        # Tab 2: PSBT
        psbt_tab = QWidget()
        psbt_layout = QVBoxLayout(psbt_tab)
        self.psbt_text_edit = QTextEdit(psbt_tab)
        self.psbt_text_edit.setPlaceholderText("Paste your PSBT in here")
        psbt_layout.addWidget(self.psbt_text_edit)
        self.psbt_button = QPushButton("Sign PSBT", psbt_tab)
        self.psbt_button.clicked.connect(self.sign)
        psbt_layout.addWidget(self.psbt_button)
        tab_widget.addTab(psbt_tab, "PSBT")

        # Tab 3: Message Signing
        message_tab = QWidget()
        message_layout = QVBoxLayout(message_tab)
        self.message_text_edit = QTextEdit(message_tab)
        self.message_text_edit.setPlaceholderText("Paste your message to be signed")
        message_layout.addWidget(self.message_text_edit)
        self.address_index_line_edit = QLineEdit(message_tab)
        self.address_index_line_edit.setText("m/84h/0h/0h/0/0")
        self.address_index_line_edit.setPlaceholderText("Address index")
        message_layout.addWidget(self.address_index_line_edit)
        self.sign_message_button = QPushButton("Sign Message", message_tab)
        self.sign_message_button.clicked.connect(self.sign_message)
        message_layout.addWidget(self.sign_message_button)
        tab_widget.addTab(message_tab, "Sign Message")

        # Initialize the network selection

        self.combo_network.currentIndexChanged.connect(self.switch_network)
        self.combo_network.setCurrentIndex(0)

    def sign_message(self):
        signed_message = self.usb.sign_message(
            self.message_text_edit.toPlainText(), self.address_index_line_edit.text()
        )
        if signed_message:
            self.message_text_edit.setText(signed_message)

    def sign(self):
        psbt = bdk.PartiallySignedTransaction(self.psbt_text_edit.toPlainText())
        self.psbt_text_edit.setText("")
        signed_psbt = self.usb.sign(psbt)
        if signed_psbt:
            self.psbt_text_edit.setText(signed_psbt.serialize())

    def on_button_clicked(self):
        self.xpubs_text_edit.setText("")
        fingerprint_and_xpus = self.usb.get_fingerprint_and_xpubs()
        if not fingerprint_and_xpus:
            return
        fingerprint, xpubs = fingerprint_and_xpus

        if xpubs:
            txt = "\n".join(
                [
                    f"{str(k)}: [{k.key_origin(self.network).replace('m/',f'{ fingerprint}/')}]  {v}"
                    for k, v in xpubs.items()
                ]
            )

            self.xpubs_text_edit.setText(txt)

    def switch_network(self, idx):
        networks = [n for n in bdk.Network]
        self.network = networks[idx]
