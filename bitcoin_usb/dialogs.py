import sys
import time
from collections.abc import Callable
from typing import Any, Generic, TypeVar

import bdkpython as bdk
from PyQt6.QtCore import QEventLoop, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QGuiApplication
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
    error = pyqtSignal(Exception)  # New signal for errors

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            func_result = self.func(*self.args, **self.kwargs)
            self.finished.emit(func_result)  # Emit the func_result if successful
        except Exception as e:
            self.error.emit(e)  # Emit error if an exception occurs


T = TypeVar("T")


class ThreadedWaitingDialog(QDialog, Generic[T]):
    def __init__(
        self,
        func: Callable[[], T],
        *args,
        title="Processing...",
        message="Please wait, processing operation...",
        **kwargs,
    ):
        super().__init__()
        self.setWindowTitle(title)
        self.setModal(True)

        self._layout = QVBoxLayout(self)
        self.label = QLabel(message)
        self._layout.addWidget(self.label)

        # Setup worker and thread
        self.worker = Worker(func, *args, **kwargs)
        self._thread = QThread()
        self.worker.moveToThread(self._thread)
        self.worker.finished.connect(self.handle_func_result)
        self.worker.error.connect(self.handle_func_error)  # Connect error signal
        self._thread.started.connect(self.worker.run)

        self.loop = QEventLoop()  # Event loop to block for synchronous execution
        self.exception = None  # To store an exception, if it occurs

    def handle_func_result(self, func_result: T):
        self.func_result = func_result
        if self.loop.isRunning():
            self.loop.exit()  # Exit the loop only if it's running

    def handle_func_error(self, exception):
        self.exception = exception
        if self.loop.isRunning():
            self.loop.exit()  # Exit the loop when an error is encountered

    def get_result(self) -> T:
        self.show()  # Show the dialog
        self._thread.start()  # Start the thread
        self.loop.exec()  # Block here until the operation finishes or errors out
        self.close()  # Close the dialog
        if self.exception:
            raise self.exception  # Re-raise the exception after closing the dialog
        return self.func_result

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
        super().closeEvent(a0)


class DeviceDialog(QDialog):
    def __init__(self, parent, devices: list[dict[str, Any]], network: bdk.Network):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Select the detected device"))
        self._layout = QVBoxLayout(self)
        self.setModal(True)

        # Creating a button for each device
        for device in devices:
            button = QPushButton(f"{device.get('type', '')} - {device.get('model', '')}", self)
            button.clicked.connect(lambda *args, d=device: self.select_device(d))
            self._layout.addWidget(button)

        self.selected_device: dict[str, Any] | None = None
        self.network = network

        # ensure the dialog has its “natural” size
        self.adjustSize()
        # get screen center
        if primaryScreen := QGuiApplication.primaryScreen():
            screen_geom = primaryScreen.availableGeometry()
            screen_center = screen_geom.center()

            # move this dialog’s frame so that its center is at screen_center
            fg = self.frameGeometry()
            fg.moveCenter(screen_center)
            self.move(fg.topLeft())

    def select_device(self, device: dict[str, Any]):
        self.selected_device = device
        self.accept()

    def get_selected_device(self) -> dict[str, Any] | None:
        return self.selected_device


if __name__ == "__main__":

    def main():
        QApplication(sys.argv)

        def f():
            time.sleep(5)
            return {"res": "res"}

        manager = ThreadedWaitingDialog(f, title="Operation In Progress", message="Processing data...")
        func_result = manager.get_result()  # Get func_result directly via method
        print("Operation completed with func_result:", func_result)

    main()
