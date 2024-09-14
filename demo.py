import sys

import bdkpython as bdk
from PyQt6.QtWidgets import QApplication

from bitcoin_usb import demo_gui

if __name__ == "__main__":
    app = QApplication(sys.argv)
    network = bdk.Network.REGTEST
    window = demo_gui.MainWindow(network)
    window.show()
    sys.exit(app.exec())
