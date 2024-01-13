import logging
import threading
from abc import ABC, abstractmethod

import hwilib.commands as hwi_commands
from hwilib.common import Chain
from hwilib.psbt import PSBT

logger = logging.getLogger(__name__)

from typing import Any, Dict

import bdkpython as bdk
from hwilib.descriptor import MultisigDescriptor as HWIMultisigDescriptor

from .address_types import (
    AddressType,
    DescriptorInfo,
    get_all_address_types,
    get_hwi_address_type,
)


class BaseDevice(ABC):
    def __init__(self, network: bdk.Network) -> None:
        self.network = network

    @abstractmethod
    def get_fingerprint(self) -> str:
        pass

    @abstractmethod
    def get_xpubs(self) -> Dict[AddressType, str]:
        pass

    @abstractmethod
    def sign_psbt(self, psbt: bdk.PartiallySignedTransaction) -> bdk.PartiallySignedTransaction:
        pass

    @abstractmethod
    def sign_message(self, message: str, bip32_path: str) -> str:
        pass

    @abstractmethod
    def display_address(
        self,
        descriptor_str: str,
        keychain: bdk.KeychainKind,
        address_index: int,
        network: bdk.Network,
    ) -> str:
        pass


class USBDevice(BaseDevice):
    def __init__(self, selected_device: Dict[str, Any], network: bdk.Network):
        super().__init__(network=network)
        self.selected_device = selected_device
        self.lock = threading.Lock()
        self.client = None

    def bdknetwork_to_chain(self, network: bdk.Network):
        if network.BITCOIN:
            return Chain.MAIN
        if network.REGTEST:
            return Chain.REGTEST
        if network.SIGNET:
            return Chain.SIGNET
        if network.TESTNET:
            return Chain.TEST

    def __enter__(self):
        self.lock.acquire()
        self.client = hwi_commands.get_client(
            device_type=self.selected_device["type"],
            device_path=self.selected_device["path"],
            chain=self.bdknetwork_to_chain(self.network),
        )
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.client:
            self.client.close()
        self.lock.release()
        # Handle exceptions if necessary
        if exc_type is not None:
            print(f"An exception occurred: {exc_value}")

    def get_fingerprint(self) -> str:
        assert self.client
        return self.client.get_master_fingerprint().hex()

    def get_xpubs(self) -> Dict[AddressType, str]:
        xpubs = {}
        for address_type in get_all_address_types():
            xpubs[address_type] = self.get_xpub(address_type.key_origin(self.network))
        return xpubs

    def get_xpub(self, key_origin: str) -> str:
        assert self.client
        return self.client.get_pubkey_at_path(key_origin).to_string()

    def sign_psbt(self, psbt: bdk.PartiallySignedTransaction) -> bdk.PartiallySignedTransaction:
        "Returns a signed psbt. However it still needs to be finalized by  a bdk wallet"
        assert self.client
        hwi_psbt = PSBT()
        hwi_psbt.deserialize(psbt.serialize())

        signed_hwi_psbt = self.client.sign_tx(hwi_psbt)

        return bdk.PartiallySignedTransaction(signed_hwi_psbt.serialize())

    def sign_message(self, message: str, bip32_path: str) -> str:
        assert self.client
        return self.client.sign_message(message, bip32_path)

    def display_address(
        self,
        descriptor_str: str,
        keychain: bdk.KeychainKind,
        address_index: int,
        network: bdk.Network,
    ) -> str:
        assert self.client
        desc_infos = DescriptorInfo.from_str(descriptor_str)

        if desc_infos.address_type.is_multisig:
            pubkey_providers = [
                signer_info.to_hwi_pubkey_provider() for signer_info in desc_infos.spk_provider
            ]
            return self.client.display_multisig_address(
                get_hwi_address_type(desc_infos.address_type),
                HWIMultisigDescriptor(
                    pubkeys=pubkey_providers,
                    thresh=desc_infos.threshold,
                    is_sorted=True,
                ),
            )
        else:
            return self.client.display_singlesig_address(
                desc_infos.address_type.get_bip32_path(network, keychain, address_index),
                get_hwi_address_type(desc_infos.address_type),
            )
