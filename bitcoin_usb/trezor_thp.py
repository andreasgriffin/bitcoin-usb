import logging
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

import hwilib.devices.trezorlib.messages as hwi_messages
import hwilib.devices.trezorlib.protobuf as hwi_protobuf
import trezorlib.protobuf as trezorlib_protobuf
from hwilib.common import AddressType, Chain
from hwilib.descriptor import MultisigDescriptor, RegisteredDescriptor
from hwilib.devices.trezor import TrezorClient as HwiTrezorClient
from hwilib.errors import (
    ActionCanceledError,
    DeviceAlreadyInitError,
    UnavailableActionError,
)
from hwilib.hwwclient import HardwareWalletClient
from hwilib.key import ExtendedKey
from hwilib.psbt import PSBT
from PyQt6 import sip
from PyQt6.QtCore import Q_ARG, QCoreApplication, QMetaObject, QObject, Qt, QThread, pyqtSlot
from PyQt6.QtWidgets import QInputDialog, QLineEdit
from trezorlib import device, messages
from trezorlib.client import AppManifest, PassphraseSetting, TrezorClient
from trezorlib.client import get_client as trezorlib_get_client
from trezorlib.models import T3W1, TrezorModel
from trezorlib.thp.client import TrezorClientThp
from trezorlib.thp.credentials import Credential
from trezorlib.thp.pairing import default_pairing_flow
from trezorlib.transport import Transport
from trezorlib.transport import all_transports as trezorlib_all_transports
from trezorlib.transport import get_transport as trezorlib_get_transport

from bitcoin_usb.i18n import translate

logger = logging.getLogger(__name__)

TREZOR_APP_NAME = "bitcoin-usb"
_V1_LOCAL_CLIENT_INTERNAL_MODELS = frozenset({T3W1.internal_name})

_PAIRING_CREDENTIALS: dict[str, Credential] = {}


@dataclass(slots=True)
class _TextRequest:
    title: str
    label: str
    echo: QLineEdit.EchoMode
    done: threading.Event = field(default_factory=threading.Event)
    value: str | None = None
    error: BaseException | None = None


class _MainThreadTextPrompt(QObject):
    @pyqtSlot(object)
    def show_text_dialog(self, payload: object) -> None:
        if not isinstance(payload, _TextRequest):
            raise TypeError(f"Unexpected payload type: {type(payload)!r}")

        try:
            payload.value = _show_text_dialog(payload.title, payload.label, payload.echo)
        except BaseException as exc:
            payload.error = exc
        finally:
            payload.done.set()


_MAIN_THREAD_TEXT_PROMPT: _MainThreadTextPrompt | None = None


def _get_main_thread_text_prompt() -> _MainThreadTextPrompt:
    global _MAIN_THREAD_TEXT_PROMPT
    if _MAIN_THREAD_TEXT_PROMPT is None or sip.isdeleted(_MAIN_THREAD_TEXT_PROMPT):
        _MAIN_THREAD_TEXT_PROMPT = _MainThreadTextPrompt()
        app = QCoreApplication.instance()
        if app is not None:
            _MAIN_THREAD_TEXT_PROMPT.moveToThread(app.thread())
    return _MAIN_THREAD_TEXT_PROMPT


def is_trezor_modern_device(device_info: dict[str, Any]) -> bool:
    return str(device_info.get("type", "")).lower() == "trezor" and (
        str(device_info.get("protocol", "")).lower() == "thp"
        or str(device_info.get("internal_model", "")) in _V1_LOCAL_CLIENT_INTERNAL_MODELS
    )


def _format_model_name(model: TrezorModel) -> str:
    return str(model.name).strip() or str(model.internal_name)


def _should_use_local_trezor_client(client: TrezorClient) -> bool:
    return (
        isinstance(client, TrezorClientThp) or client.model.internal_name in _V1_LOCAL_CLIENT_INTERNAL_MODELS
    )


def _enumerate_trezor_transports() -> list[Transport]:
    devices: list[Transport] = []
    for transport_cls in trezorlib_all_transports():
        if transport_cls.PATH_PREFIX == "ble":
            continue
        try:
            devices.extend(list(transport_cls.enumerate()))
        except Exception as exc:
            logger.debug(
                "Skipping failed Trezor transport enumeration for %s: %s", transport_cls.__name__, exc
            )
    return devices


def enumerate_trezor_thp_devices() -> list[dict[str, Any]]:
    app = AppManifest(app_name=TREZOR_APP_NAME)
    devices: list[dict[str, Any]] = []

    for transport in _enumerate_trezor_transports():
        path = transport.get_path()
        if path.startswith("ble:"):
            transport.close()
            continue
        try:
            client = trezorlib_get_client(app, transport)
            if not _should_use_local_trezor_client(client):
                continue

            devices.append(
                {
                    "type": "trezor",
                    "path": path,
                    "model": _format_model_name(client.model),
                    "internal_model": client.model.internal_name,
                    "protocol": "thp" if isinstance(client, TrezorClientThp) else "v1",
                    "transport": "usb",
                    "label": _format_model_name(client.model),
                }
            )
        except Exception as exc:
            logger.debug("Skipping unsupported Trezor transport %s: %s", path, exc)
        finally:
            transport.close()

    return devices


def _show_text_dialog(title: str, label: str, echo: QLineEdit.EchoMode = QLineEdit.EchoMode.Normal) -> str:
    text, accepted = QInputDialog.getText(None, title, label, echo)
    if not accepted:
        raise ActionCanceledError(f"{title} canceled")

    value = text.strip()
    if not value:
        raise ActionCanceledError(f"{title} canceled")
    return value


def _request_text(title: str, label: str, echo: QLineEdit.EchoMode = QLineEdit.EchoMode.Normal) -> str:
    app = QCoreApplication.instance()
    if app is None or QThread.currentThread() is app.thread():
        return _show_text_dialog(title, label, echo)

    text_request = _TextRequest(title=title, label=label, echo=echo)
    QMetaObject.invokeMethod(
        _get_main_thread_text_prompt(),
        "show_text_dialog",
        Qt.ConnectionType.QueuedConnection,
        Q_ARG(object, text_request),
    )
    text_request.done.wait()

    if text_request.error is not None:
        raise text_request.error
    if text_request.value is None:
        raise ActionCanceledError(f"{title} canceled")
    return text_request.value


def _request_pairing_code() -> str:
    return _request_text(
        translate("trezor", "Pair Trezor"),
        translate("trezor", "Enter the 6-digit pairing code shown on the Trezor:"),
    )


def _request_pin(_message: messages.PinMatrixRequest) -> str:
    return _request_text(
        translate("trezor", "Unlock Trezor"),
        translate("trezor", "Enter the PIN using the Trezor keypad layout (7 8 9 / 4 5 6 / 1 2 3):"),
        QLineEdit.EchoMode.Password,
    )


def _convert_message_type(message_type: type[Any], target_messages_module: Any) -> type[Any]:
    converted_type = target_messages_module.__dict__.get(message_type.__name__)
    if not isinstance(converted_type, type):
        raise TypeError(f"Unable to convert protobuf message type {message_type.__name__}")
    return converted_type


def _convert_message_instance(
    message: Any,
    source_protobuf_module: Any,
    target_protobuf_module: Any,
    target_messages_module: Any,
) -> Any:
    converted_type = _convert_message_type(type(message), target_messages_module)
    buffer = BytesIO()
    source_protobuf_module.dump_message(buffer, message)
    buffer.seek(0)
    return target_protobuf_module.load_message(buffer, converted_type)


class _HwiMessageBridge:
    def __init__(self, session: Any, features: messages.Features, version: tuple[int, ...]) -> None:
        self._session = session
        self.features = features
        self.version = version

    def open(self) -> None:
        # The outer THP wallet session is already active.
        return None

    def close(self) -> None:
        # HWI's low-level helpers wrap calls in their own session decorator.
        # For THP reuse we keep that API shape, but the actual session lifetime
        # is owned by `TrezorThpClient._wallet_session()`.
        return None

    def call(self, message: Any, check_fw: bool = True) -> Any:
        _ = check_fw
        trezorlib_message = _convert_message_instance(
            message,
            hwi_protobuf,
            trezorlib_protobuf,
            messages,
        )
        response = self._session.call(trezorlib_message)
        return _convert_message_instance(
            response,
            trezorlib_protobuf,
            hwi_protobuf,
            hwi_messages,
        )


class _HwiTrezorSessionAdapter:
    """
    Minimal adapter that lets us reuse HWI's maintained Trezor PSBT logic.

    HWI's `TrezorClient.sign_tx()` only depends on a few attributes/methods:
    a connected client-like object, the chain/coin name, and `_supports_external()`.
    THP wallet operations run through a derived session instead of the base client,
    so we adapt that session to the HWI interface here instead of forking `sign_tx`.
    """

    def __init__(self, client: "TrezorThpClient", session: Any) -> None:
        self.client = _HwiMessageBridge(session, client.features, client.client.version)
        self.chain = client.chain
        self.coin_name = client._coin_name(client.chain)

    def _check_unlocked(self) -> None:
        self.coin_name = TrezorThpClient._coin_name(self.chain)

    def _supports_external(self) -> bool:
        return HwiTrezorClient._supports_external(self)  # type: ignore


class TrezorThpClient(HardwareWalletClient):
    def __init__(
        self,
        path: str,
        password: str | None = None,
        expert: bool = False,
        chain: Chain = Chain.MAIN,
    ) -> None:
        normalized_password = "" if password is None else password
        super().__init__(path, normalized_password, expert, chain)
        self.client = self._create_client()
        self.type = "Trezor"

    def _create_client(self):
        credentials: Sequence[Credential] = ()
        cached = _PAIRING_CREDENTIALS.get(self.path)
        if cached is not None:
            credentials = (cached,)

        app = AppManifest(
            app_name=TREZOR_APP_NAME,
            credentials=credentials,
            pin_callback=_request_pin,
        )
        transport = trezorlib_get_transport(self.path, prefix_search=True)
        client = trezorlib_get_client(app, transport)

        if client.pairing.is_paired():
            return client

        credential = default_pairing_flow(
            client.pairing,
            code_entry_callback=_request_pairing_code,
            request_credential=True,
        )
        if credential is not None:
            _PAIRING_CREDENTIALS[self.path] = credential
        return client

    @property
    def features(self) -> messages.Features:
        return self.client.features

    def refresh_features(self) -> messages.Features:
        return self.client.refresh_features()

    def _wallet_session(self):
        passphrase: str | PassphraseSetting
        if self.password:
            passphrase = self.password
        else:
            passphrase = PassphraseSetting.STANDARD_WALLET
        return self.client.get_session(passphrase=passphrase)

    def _management_session(self):
        return self.client.get_session(passphrase=PassphraseSetting.NONE)

    @staticmethod
    def _coin_name(chain: Chain) -> str:
        if chain == Chain.MAIN:
            return "Bitcoin"
        return "Testnet"

    def get_pubkey_at_path(self, bip32_path: str) -> ExtendedKey:
        with self._wallet_session() as session:
            return HwiTrezorClient.get_pubkey_at_path(_HwiTrezorSessionAdapter(self, session), bip32_path)

    def sign_tx(self, psbt: PSBT, registered_descriptors: set[RegisteredDescriptor] | None = None) -> PSBT:
        with self._wallet_session() as session:
            return HwiTrezorClient.sign_tx(
                _HwiTrezorSessionAdapter(self, session), psbt, registered_descriptors
            )

    def sign_message(self, message: str | bytes, bip32_path: str) -> str:
        with self._wallet_session() as session:
            return HwiTrezorClient.sign_message(_HwiTrezorSessionAdapter(self, session), message, bip32_path)

    def display_singlesig_address(self, bip32_path: str, addr_type: AddressType) -> str:
        with self._wallet_session() as session:
            return HwiTrezorClient.display_singlesig_address(
                _HwiTrezorSessionAdapter(self, session),
                bip32_path,
                addr_type,
            )

    def display_multisig_address(self, addr_type: AddressType, multisig: MultisigDescriptor) -> str:
        with self._wallet_session() as session:
            return HwiTrezorClient.display_multisig_address(
                _HwiTrezorSessionAdapter(self, session),
                addr_type,
                multisig,
            )

    def wipe_device(self) -> bool:
        with self._management_session() as session:
            device.wipe(session)
        return True

    def setup_device(self, label: str = "", passphrase: str = "") -> bool:
        if self.features.initialized:
            raise DeviceAlreadyInitError("Device is already initialized. Use wipe first and try again")

        with self._management_session() as session:
            device.reset(session, label=label or None, passphrase_protection=bool(passphrase))
        return True

    def restore_device(self, label: str = "", word_count: int = 24) -> bool:
        with self._management_session() as session:
            device.recover(
                session,
                word_count=word_count,
                label=label or None,
                passphrase_protection=bool(self.password),
            )
        return True

    def backup_device(self, label: str = "", passphrase: str = "") -> bool:
        raise UnavailableActionError(f"The {self.type} does not support creating a backup via software")

    def close(self) -> None:
        self.client.transport.close()

    def prompt_pin(self) -> bool:
        raise UnavailableActionError("PIN prompting is handled by the Trezor THP connection flow")

    def send_pin(self, pin: str) -> bool:
        raise UnavailableActionError("PIN entry is handled during the Trezor THP connection flow")

    def toggle_passphrase(self) -> bool:
        raise UnavailableActionError("Passphrase toggling is not implemented for the THP client")

    def can_sign_taproot(self) -> bool:
        return True
