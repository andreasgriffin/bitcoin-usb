import logging
import threading
from abc import abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

import bdkpython as bdk
import hwilib.commands as hwi_commands
from bitcoin_safe_lib.async_tools.loop_in_thread import LoopInThread
from hwilib.common import Chain
from hwilib.devices.bitbox02 import Bitbox02Client, CLINoiseConfig
from hwilib.devices.bitbox02_lib import bitbox02
from hwilib.devices.bitbox02_lib.communication import devices as bitbox02devices
from hwilib.devices.trezor import TrezorClient
from hwilib.hwwclient import HardwareWalletClient
from hwilib.psbt import PSBT
from PyQt6.QtCore import QEventLoop, QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from bitcoin_usb.dialogs import Worker
from bitcoin_usb.i18n import translate
from bitcoin_usb.util import run_device_task, run_script

from .address_types import (
    AddressType,
    DescriptorInfo,
    SortedMultisigDescriptor,
    get_all_address_types,
    get_hwi_address_type,
)

logger = logging.getLogger(__name__)


def create_custom_message_box(
    icon: QMessageBox.Icon,
    title: str | None,
    text: str | None,
    buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
    parent: QWidget | None = None,
    flags: Qt.WindowType = Qt.WindowType.Widget,
):
    msg_box = QMessageBox(parent)
    msg_box.setModal(False)
    msg_box.setIcon(icon)
    msg_box.setWindowTitle(title if title is not None else "Message")
    msg_box.setText(text if text is not None else "Details are missing.")
    msg_box.setStandardButtons(buttons)
    msg_box.setWindowFlags(flags)
    msg_box.exec()


def question_dialog(
    text="",
    title="Question",
    buttons=QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
) -> bool:
    msg_box = QMessageBox()
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setIcon(QMessageBox.Icon.Question)

    # Set the QDialogButtonBox as the standard button in the message box
    msg_box.setStandardButtons(buttons)

    # Execute the message box
    ret = msg_box.exec()

    # Check which button was clicked
    if ret == QMessageBox.StandardButton.Yes:
        return True
    elif ret == QMessageBox.StandardButton.No:
        return False
    elif ret == QMessageBox.StandardButton.Cancel:
        return False
    return False


class ThreadedCapturePrintDialogBitBox02(QDialog):
    print_message = pyqtSignal(str)

    def __init__(self, func, *args, title="Processing...", message="", **kwargs):
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
        self._thread.started.connect(self.worker.run)

        self.loop = QEventLoop()  # Event loop to block for synchronous execution

        self.dialog_loop = QEventLoop()
        self.print_message.connect(self.add_text)
        self.button_click_result: bool | None = None

        # Add dialog buttons
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._layout.addWidget(self.buttonBox)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def handle_func_result(self, result):
        self.func_result = result
        if self.loop.isRunning():
            self.loop.exit()  # Exit the loop only if it's running

    def add_text(self, s: str):
        old_text = self.label.text()
        self.label.setText(old_text + "\n\n" + s)

    def accept(self):
        self.button_click_result = True
        self.dialog_loop.exit(0)  # Stop the event loop
        super().accept()

    def reject(self):
        self.button_click_result = False
        self.dialog_loop.exit(0)  # Stop the event loop
        super().reject()

    def get_result(self) -> bool:
        self.show()  # Show the dialog

        self._thread.start()  # Start the thread
        self.loop.exec()  # Block here until the operation finishes

        # if no button was clicked yet, then block until one is clicked
        if self.button_click_result is None:
            self.dialog_loop.exec()  # This will block here until loop.exit() is called

        total_result = all((self.func_result, bool(self.button_click_result)))

        self.end_thread()
        return total_result

    def end_thread(self):
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()


def bdknetwork_to_chain(network: bdk.Network):
    if network == bdk.Network.BITCOIN:
        return Chain.MAIN
    elif network == bdk.Network.REGTEST:
        return Chain.REGTEST
    elif network == bdk.Network.SIGNET:
        return Chain.SIGNET
    elif network in [bdk.Network.TESTNET, bdk.Network.TESTNET4]:
        return Chain.TEST
    raise ValueError(f"Could not convert the {network=}")


class BaseDevice:
    def __init__(self, network: bdk.Network) -> None:
        self.network = network

    @abstractmethod
    def get_fingerprint(self) -> str:
        pass

    @abstractmethod
    def get_xpubs(self) -> dict[AddressType, str]:
        pass

    @abstractmethod
    def sign_psbt(self, psbt: bdk.Psbt) -> bdk.Psbt | None:
        pass

    @abstractmethod
    def sign_message(self, message: str, bip32_path: str) -> str:
        pass

    @abstractmethod
    def display_address(
        self,
        address_descriptor: str,
    ) -> str:
        pass


class DialogNoiseConfig(CLINoiseConfig):
    """Noise pairing and attestation check handling in the terminal (stdin/stdout)"""

    def show_pairing(self, code: str, device_response: Callable[[], bool]) -> bool:
        self.threaded_dialog = ThreadedCapturePrintDialogBitBox02(
            func=device_response,
            title=translate("usb", "Pair Bitbox02"),
        )
        self.threaded_dialog.add_text(
            translate(
                "usb",
                "Please compare and confirm the pairing code on your BitBox02:\n\n{code}",
            ).format(code=code)
        )
        result = self.threaded_dialog.get_result()

        return result

    def attestation_check(self, result: bool) -> None:
        if result:
            logger.info("BitBox02 attestation check PASSED\n")
        else:
            logger.info("BitBox02 attestation check FAILED")
            create_custom_message_box(
                QMessageBox.Icon.Critical,
                "BitBox02 attestation check FAILED",
                text="Your BitBox02 might not be genuine. Please contact support@shiftcrypto.ch if the problem persists.",
            )


class USBDevice(BaseDevice, QObject):
    def __init__(
        self,
        selected_device: dict[str, Any],
        network: bdk.Network,
        loop_in_thread: LoopInThread | None = None,
        initalization_label: str = "",
    ):
        QObject.__init__(self)
        BaseDevice.__init__(self, network=network)
        self.initalization_label = initalization_label
        self.selected_device = selected_device
        self.lock = threading.Lock()
        self.loop_in_thread = loop_in_thread
        self.client: HardwareWalletClient | None = None

    @staticmethod
    def is_bitbox02_initialized(client):
        if not isinstance(client, Bitbox02Client):
            return
        for device_info in bitbox02devices.get_any_bitbox02s():
            if device_info["path"].decode() != client.device_path:
                continue

            bb02 = bitbox02.BitBox02(  # type: ignore
                transport=client.transport,
                device_info=device_info,
                noise_config=client.noise_config,
            )
            return bb02.device_info()["initialized"]

    @classmethod
    def write_down_seed(cls, client: Bitbox02Client) -> bool | None:
        if not isinstance(client, Bitbox02Client):
            return None

        try:
            return client.backup_device()
        except Exception:
            # the user canceled the backing up, so ask again
            return False

    @classmethod
    def write_down_seed_ask_until_success(cls, client: Bitbox02Client) -> bool | None:
        if not isinstance(client, Bitbox02Client):
            return None
        while question_dialog(
            "Do you want to show the mnemonic seed to back it up on paper?",
            title="Show Seed?",
        ):
            success = cls.write_down_seed(client)
            if success:
                return success
        return False

    def _init_client(self):
        self.client = hwi_commands.get_client(
            device_type=self.selected_device["type"],
            device_path=self.selected_device["path"],
            chain=bdknetwork_to_chain(self.network),
        )

        if isinstance(self.client, TrezorClient):
            self.client.client.refresh_features()
            filepath = Path(__file__).parent / "device_scripts" / "trezor_firmware.py"
            if not filepath.exists():
                logger.error(
                    f"{filepath} could not be found. This file is necessary for initialization of trezor without prior firmware."
                )
            if self.client.client.features.bootloader_mode:
                if not filepath.exists():
                    raise Exception(
                        f"{filepath} could not be found. This file is necessary for initialization of trezor without prior firmware."
                    )
                output, error = run_script(filepath, args=["--path", self.selected_device["path"]])
                logger.debug(f"{filepath} returned {output=}")
                # the error appears even if the firmware was instralled successfully.
                # So do not raise an exception
                logger.error(f"{filepath} returned {error=}")

            if not self.client.client.features.initialized:
                if question_dialog(
                    text=self.tr("Do you want to restore an existing seed onto the device?"),
                    buttons=QMessageBox.StandardButton.No | QMessageBox.StandardButton.Yes,
                ):
                    self.client.restore_device(label=self.initalization_label)
                else:
                    self.client.setup_device(label=self.initalization_label)

        # the bitbox02 initialization works only
        # if i access the bitbox02 class directly and
        # inject the DialogNoiseConfig (default is cli)
        # to show a nice dialog message
        if isinstance(self.client, Bitbox02Client):
            self.noise_config = DialogNoiseConfig()
            self.client.noise_config = self.noise_config
            if not self.is_bitbox02_initialized(self.client):
                if question_dialog(
                    text=self.tr("Do you want to restore an existing seed onto the device?"),
                    buttons=QMessageBox.StandardButton.No | QMessageBox.StandardButton.Yes,
                ):
                    self.client.restore_device(label=self.initalization_label)
                else:
                    self.client.setup_device(label=self.initalization_label)
                    self.write_down_seed_ask_until_success(self.client)

    def __enter__(self):
        self.lock.acquire()
        try:
            # _init_client is a synchronous function; we just use the common runner
            run_device_task(loop_in_thread=self.loop_in_thread, task=self._init_client)
            return self
        except Exception:
            self.lock.release()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        if self.client:
            self.client.close()
        self.lock.release()
        # Handle exceptions if necessary
        if exc_type is not None:
            print(f"An exception occurred: {exc_value}")

    def wipe_device(self) -> bool:
        assert self.client
        return self.client.wipe_device()

    def get_fingerprint(self) -> str:
        assert self.client
        return self.client.get_master_fingerprint().hex()

    def get_xpubs(self) -> dict[AddressType, str]:
        xpubs = {}
        for address_type in get_all_address_types():
            xpubs[address_type] = self.get_xpub(address_type.key_origin(self.network))
        return xpubs

    def get_xpub(self, key_origin: str) -> str:
        assert self.client
        return self.client.get_pubkey_at_path(key_origin).to_string()

    def sign_psbt(self, psbt: bdk.Psbt) -> bdk.Psbt:
        "Returns a signed psbt. However it still needs to be finalized by  a bdk wallet"
        assert self.client
        hwi_psbt = PSBT()
        hwi_psbt.deserialize(psbt.serialize())

        signed_hwi_psbt = self.client.sign_tx(hwi_psbt)

        return bdk.Psbt(signed_hwi_psbt.serialize())

    def sign_message(self, message: str, bip32_path: str) -> str:
        assert self.client
        return self.client.sign_message(message, bip32_path)

    def display_address(
        self,
        address_descriptor: str,
    ) -> str:
        "Requires to have 1 derivation_path, like '/0/0', not '/<0;1>/*', and not '/0/*'"
        assert self.client
        desc_infos = DescriptorInfo.from_str(address_descriptor)

        if desc_infos.address_type.is_multisig:
            pubkey_providers = [
                spk_provider.to_hwi_pubkey_provider() for spk_provider in desc_infos.spk_providers
            ]
            return self.client.display_multisig_address(
                get_hwi_address_type(desc_infos.address_type),
                SortedMultisigDescriptor(
                    pubkeys=pubkey_providers,
                    thresh=desc_infos.threshold,
                ),
            )
        else:
            return hwi_commands.displayaddress(self.client, desc=address_descriptor)["address"]
