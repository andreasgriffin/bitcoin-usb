from typing import Optional

import bdkpython as bdk
from PyQt6.QtWidgets import (
    QComboBox,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bitcoin_usb.gui import USBGui


class ToolGui(QMainWindow):
    def __init__(self, network: bdk.Network):
        super().__init__()
        self.setWindowTitle(self.tr("USB Signer Tools"))
        self.usb = USBGui(network=network)

        main_widget = QWidget()
        main_widget_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        self.combo_network = QComboBox(self)
        for n in bdk.Network:
            self.combo_network.addItem(n.name, userData=n)
        self.combo_network.setCurrentText(network.name)
        main_widget_layout.addWidget(self.combo_network)

        # Create a tab widget and set it as the central widget
        tab_widget = QTabWidget(self)
        main_widget_layout.addWidget(tab_widget)

        # Tab 1: XPUBs
        xpubs_tab = QWidget()
        xpubs_layout = QVBoxLayout(xpubs_tab)
        self.button = QPushButton(self.tr("Get xpubs"), xpubs_tab)
        self.button.clicked.connect(self.on_button_clicked)
        xpubs_layout.addWidget(self.button)
        self.xpubs_text_edit = QTextEdit(xpubs_tab)
        self.xpubs_text_edit.setReadOnly(True)
        xpubs_layout.addWidget(self.xpubs_text_edit)
        tab_widget.addTab(xpubs_tab, self.tr("XPUBs"))

        # Tab 2: PSBT
        psbt_tab = QWidget()
        psbt_layout = QVBoxLayout(psbt_tab)
        self.psbt_text_edit = QTextEdit(psbt_tab)
        self.psbt_text_edit.setPlaceholderText(self.tr("Paste your PSBT in here"))
        psbt_layout.addWidget(self.psbt_text_edit)
        self.psbt_button = QPushButton(self.tr("Sign PSBT"), psbt_tab)
        self.psbt_button.clicked.connect(self.sign)
        psbt_layout.addWidget(self.psbt_button)
        tab_widget.addTab(psbt_tab, self.tr("PSBT"))

        # Tab 3: Message Signing
        message_tab = QWidget()
        message_layout = QVBoxLayout(message_tab)
        self.message_text_edit = QTextEdit(message_tab)
        self.message_text_edit.setPlaceholderText(self.tr("Paste your text to be signed"))
        message_layout.addWidget(self.message_text_edit)
        self.message_address_index_line_edit = QLineEdit(message_tab)
        self.message_address_index_line_edit.setText("m/84h/0h/0h/0/0")
        self.message_address_index_line_edit.setPlaceholderText(self.tr("Address index"))
        message_layout.addWidget(self.message_address_index_line_edit)
        self.sign_message_button = QPushButton(self.tr("Sign Message"), message_tab)
        self.sign_message_button.clicked.connect(self.sign_message)
        message_layout.addWidget(self.sign_message_button)
        tab_widget.addTab(message_tab, self.tr("Sign Message"))

        # Tab 4: Show Address
        address_tab = QWidget()
        address_tab.setLayout(QVBoxLayout())
        self.descriptor_text_edit = QTextEdit(address_tab)
        self.descriptor_text_edit.setPlaceholderText(self.tr("Paste your descriptor to be signed"))
        address_tab.layout().addWidget(self.descriptor_text_edit)
        self.display_address_button = QPushButton(self.tr("Display Address"), address_tab)
        self.display_address_button.clicked.connect(self.display_address)
        address_tab.layout().addWidget(self.display_address_button)
        tab_widget.addTab(address_tab, self.tr("Display Address"))

        # Tab 5: Wipe device
        wipe_tab = QWidget()
        wipe_tab.setLayout(QVBoxLayout())
        self.display_address_button = QPushButton(self.tr("Wipe Device"), wipe_tab)
        self.display_address_button.clicked.connect(self.wipe_device)
        wipe_tab.layout().addWidget(self.display_address_button)
        tab_widget.addTab(wipe_tab, self.tr("Wipe Device"))

        # Initialize the network selection

        self.combo_network.currentIndexChanged.connect(
            lambda idx: self.usb.set_network(bdk.Network[self.combo_network.currentText()])
        )

    def wipe_device(self) -> Optional[bool]:
        return self.usb.wipe_device()

    def display_address(self) -> Optional[str]:
        return self.usb.display_address(address_descriptor=self.descriptor_text_edit.toPlainText())

    def sign_message(self):
        signed_message = self.usb.sign_message(
            self.message_text_edit.toPlainText(), self.message_address_index_line_edit.text()
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
        device, fingerprint, xpubs = fingerprint_and_xpus

        if xpubs:
            txt = "\n".join(
                [
                    f"{str(k)}: [{k.key_origin(self.usb.network).replace('m/',f'{ fingerprint}/')}]  {v}"
                    for k, v in xpubs.items()
                ]
            )

            self.xpubs_text_edit.setText(txt)
