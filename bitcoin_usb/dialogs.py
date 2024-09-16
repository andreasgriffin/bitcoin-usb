import sys
import time
from typing import Any, Dict, List

import bdkpython as bdk
from PyQt6.QtCore import QEventLoop, QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


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

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        # Run the passed function with its arguments
        result = self.func(*self.args, **self.kwargs)
        self.finished.emit(result)  # Emit the signal with the result


class ThreadedWaitingDialog(QDialog):
    def __init__(
        self, func, *args, title="Processing...", message="Please wait, processing operation...", **kwargs
    ):
        super().__init__()
        self.setWindowTitle(title)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.label = QLabel(message)
        layout.addWidget(self.label)

        # Setup worker and thread
        self.worker = Worker(func, *args, **kwargs)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.worker.finished.connect(self.handle_result)
        self.thread.started.connect(self.worker.run)

        self.loop = QEventLoop()  # Event loop to block for synchronous execution

    def handle_result(self, result):
        self.result = result
        if self.loop.isRunning():
            self.loop.exit()  # Exit the loop only if it's running

    def get_result(self):
        self.show()  # Show the dialog
        self.thread.start()  # Start the thread
        self.loop.exec()  # Block here until the operation finishes
        self.close()  # Close the dialog
        return self.result

    def closeEvent(self, event):
        if self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()
        event.accept()  # Ensure the event is accepted after cleanup


class DeviceDialog(QDialog):
    def __init__(self, parent, devices: List[Dict[str, Any]], network: bdk.Network):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Select the detected device"))
        self.layout = QVBoxLayout(self)
        self.setModal(True)

        # Creating a button for each device
        for device in devices:
            button = QPushButton(f"{device.get('type', '')} - {device.get('model', '')}", self)
            button.clicked.connect(lambda *args, d=device: self.select_device(d))
            self.layout.addWidget(button)

        self.selected_device = None
        self.network = network

    def select_device(self, device):
        self.selected_device = device
        self.accept()

    def get_selected_device(self):
        return self.selected_device


if __name__ == "__main__":

    def main():
        QApplication(sys.argv)

        def f():
            time.sleep(5)
            return {"res": "res"}

        manager = ThreadedWaitingDialog(f, title="Operation In Progress", message="Processing data...")
        result = manager.get_result()  # Get result directly via method
        print("Operation completed with result:", result)

    main()
