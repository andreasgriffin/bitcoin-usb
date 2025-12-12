import sys

import bdkpython as bdk
from bitcoin_safe_lib.async_tools.loop_in_thread import LoopInThread
from PyQt6.QtWidgets import QApplication

from bitcoin_usb import tool_gui

if __name__ == "__main__":
    app = QApplication(sys.argv)
    network = bdk.Network.REGTEST
    loop_in_thread = LoopInThread()
    window = tool_gui.ToolGui(network, loop_in_thread)
    window.show()
    sys.exit(app.exec())
