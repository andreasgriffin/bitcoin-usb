import sys
from typing import Dict
from PySide2.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QDialog,
    QVBoxLayout,
    QTextEdit,
    QLineEdit,
    QTabWidget,
)
import hwilib.commands as hwi_commands
from .device import USBDevice
import bdkpython as bdk
from PySide2.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QTextEdit,
    QComboBox,
)


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


class MainWindow(QMainWindow):
    def __init__(self, network):
        super().__init__()
        self.network = network

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
        self.address_index_line_edit.setPlaceholderText("Address index")
        message_layout.addWidget(self.address_index_line_edit)
        self.sign_message_button = QPushButton("Sign Message", message_tab)
        message_layout.addWidget(self.sign_message_button)
        tab_widget.addTab(message_tab, "Sign Message")

        # Initialize the network selection

        self.combo_network.currentIndexChanged.connect(self.switch_network)
        self.combo_network.setCurrentIndex(0)

    def get_device(self) -> Dict:
        devices = hwi_commands.enumerate()
        dialog = DeviceDialog(self, devices, self.network)
        if dialog.exec_():
            return dialog.get_selected_device()

    def sign(self):
        psbt = bdk.PartiallySignedTransaction(self.psbt_text_edit.toPlainText())
        self.psbt_text_edit.setText("")
        selected_device = self.get_device()
        if selected_device:
            with USBDevice(selected_device, self.network) as dev:
                signed_psbt = dev.sign_psbt(psbt)
                self.psbt_text_edit.setText(signed_psbt.serialize())

    def on_button_clicked(self):
        self.xpubs_text_edit.setText("")
        selected_device = self.get_device()
        if selected_device:
            self.display_xpubs(selected_device)

    def display_xpubs(self, device):
        txt = ""
        with USBDevice(device, self.network) as dev:
            xpubs = dev.get_xpubs()
            txt += "\n".join(
                [
                    f"{str(k)}: [{k.key_origin(self.network).replace('m/',f'{ dev.get_fingerprint()}/')}]  {v}"
                    for k, v in xpubs.items()
                ]
            )

        self.xpubs_text_edit.setText(txt)

    def switch_network(self, idx):
        networks = [n for n in bdk.Network]
        self.network = networks[idx]
