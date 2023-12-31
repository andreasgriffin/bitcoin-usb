import logging
from typing import Dict, List
import bdkpython as bdk

logger = logging.getLogger(__name__)
from bitcointx.core.psbt import (
    PartiallySignedTransaction as TXPartiallySignedTransaction,
)
from bitcointx import select_chain_params
import base64
from bitcointx.wallet import CCoinExtKey
from bitcointx.core.key import KeyStore, BIP32PathTemplate

from .address_types import (
    AddressType,
    AddressTypes,
    get_all_address_types,
)
from .seed_tools import derive, get_bip32_ext_private_key
from .device import BaseDevice


class SoftwareSigner(BaseDevice):
    def __init__(self, mnemonic: str, network: bdk.Network) -> None:
        super().__init__(network=network)
        self.mnemonic = mnemonic

    def get_fingerprint(self) -> str:
        # it doesn't mattrer which AddressTypes i choose, because the fingerprint is identical for all
        address_type = AddressTypes.p2wsh
        xpub, fingerprint = derive(self.mnemonic, address_type.key_origin(self.network), self.network)
        return fingerprint

    def get_xpubs(self) -> Dict[AddressType, str]:
        xpubs = {}
        for address_type in get_all_address_types():
            xpub, fingerprint = derive(self.mnemonic, address_type.key_origin(self.network), self.network)
            xpubs[address_type] = xpub
        return xpubs

    def _extract_derivation_paths(self, input_psbt: bdk.PartiallySignedTransaction) -> List["str"]:
        import json

        psbt_json = json.loads(input_psbt.json_serialize())

        derivation_paths = []

        # Extract input derivation paths from the "bip32_derivation" field in each input
        for input_data in psbt_json["inputs"]:
            bip32_derivation = input_data.get("bip32_derivation")
            if bip32_derivation:
                for derivation_info in bip32_derivation:
                    path = derivation_info[1][-1]  # Get the last element of the path
                    derivation_paths.append(path)

        return derivation_paths

    def sign_psbt(self, input_psbt: bdk.PartiallySignedTransaction) -> bdk.PartiallySignedTransaction:
        # Select network parameters
        network_params = {
            bdk.Network.BITCOIN: "bitcoin",
            bdk.Network.TESTNET: "bitcoin/testnet",
            bdk.Network.REGTEST: "bitcoin/regtest",
            bdk.Network.SIGNET: "bitcoin/signet",
        }
        select_chain_params(network_params.get(self.network, "bitcoin"))

        # Base64-encoded PSBT
        base64_encoded_psbt = input_psbt.serialize()

        # Deserialize the PSBT
        psbt = TXPartiallySignedTransaction.from_base64_or_binary(base64_encoded_psbt)

        # Get BIP32 extended private key
        bip32_ext_private_key = get_bip32_ext_private_key(self.mnemonic, network=self.network)

        # Convert the BIP32 key to an internal usable format
        ext_key = CCoinExtKey(bip32_ext_private_key)

        # Create a keystore and add the extended key with the path template
        keystore = KeyStore()
        for path in self._extract_derivation_paths(input_psbt):
            # Define a path template for the key
            keystore.add_key((ext_key, BIP32PathTemplate(path)))

        # Sign the PSBT
        psbt.sign(keystore)

        # Check if the PSBT is finalized (optional, based on your requirements)
        # If not finalized, you might want to handle it differently

        # Serialize the PSBT after signing
        signed_psbt = psbt.serialize()

        # Encode the signed PSBT back to Base64
        signed_base64_psbt = base64.b64encode(signed_psbt).decode()

        return bdk.PartiallySignedTransaction(signed_base64_psbt)

    def sign_message(self, message: str, bip32_path: str) -> str:
        raise NotImplementedError("")

    def display_address(
        self,
        descriptor_str: str,
        keychain: bdk.KeychainKind,
        address_index: int,
        network: bdk.Network,
    ):
        pass
