import sys

import bdkpython as bdk
from PySide2.QtWidgets import QApplication

from bitcoin_usb import gui

if __name__ == "__main__":
    app = QApplication(sys.argv)
    network = bdk.Network.REGTEST
    window = gui.MainWindow(network)
    window.show()
    sys.exit(app.exec_())
