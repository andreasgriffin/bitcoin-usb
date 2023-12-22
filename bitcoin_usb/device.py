import logging
import threading

import hwilib.commands as hwi_commands
from hwilib.common import Chain
from hwilib.psbt import PSBT
from hwilib.descriptor import Descriptor, PubkeyProvider
from usb1 import USBError

logger = logging.getLogger(__name__)

import bdkpython as bdk

from typing import *
from .address_types import (
    AddressType,
    AddressTypes,
    DescriptorInfo,
    SimplePubKeyProvider,
    get_all_address_types,
    get_hwi_address_type,
)
from hwilib.descriptor import MultisigDescriptor as HWIMultisigDescriptor


class BaseDevice:
    def __init__(self, network: bdk.Network) -> None:
        self.network = network

    def get_fingerprint(self) -> str:
        pass

    def get_xpubs(self) -> Dict[AddressTypes, str]:
        pass

    def sign_psbt(
        self, psbt: bdk.PartiallySignedTransaction
    ) -> bdk.PartiallySignedTransaction:
        pass

    def sign_message(self, message: str, bip32_path: str) -> str:
        pass

    def display_address(
        self,
        descriptor_str: str,
        keychain: bdk.KeychainKind,
        address_index: int,
        network: bdk.Network,
    ) -> str:
        pass


class USBDevice(BaseDevice):
    def __init__(self, enumerate_device: List[Dict[str, Any]], network: bdk.Network):
        super().__init__(network=network)
        self.enumerate_device = enumerate_device
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
            device_type=self.enumerate_device["type"],
            device_path=self.enumerate_device["path"],
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
        return self.client.get_master_fingerprint().hex()

    def get_xpubs(self) -> Dict[AddressTypes, str]:
        xpubs = {}
        for address_type in get_all_address_types():
            xpubs[address_type] = self.client.get_pubkey_at_path(
                address_type.key_origin(self.network)
            ).to_string()
        return xpubs

    def sign_psbt(
        self, psbt: bdk.PartiallySignedTransaction
    ) -> bdk.PartiallySignedTransaction:
        "Returns a signed psbt. However it still needs to be finalized by  a bdk wallet"
        hwi_psbt = PSBT()
        hwi_psbt.deserialize(psbt.serialize())

        signed_hwi_psbt = self.client.sign_tx(hwi_psbt)

        return bdk.PartiallySignedTransaction(signed_hwi_psbt.serialize())

    def sign_message(self, message: str, bip32_path: str) -> str:
        return self.client.sign_message(message, bip32_path)

    def display_address(
        self,
        descriptor_str: str,
        keychain: bdk.KeychainKind,
        address_index: int,
        network: bdk.Network,
    ) -> str:
        desc_infos = DescriptorInfo.from_str(descriptor_str)

        if desc_infos.address_type.is_multisig:
            pubkey_providers = [
                signer_info.to_hwi_pubkey_provider()
                for signer_info in desc_infos.spk_provider
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
                desc_infos.address_type.get_bip32_path(
                    network, keychain, address_index
                ),
                get_hwi_address_type(desc_infos.address_type),
            )
