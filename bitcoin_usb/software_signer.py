import logging
from typing import cast

import bdkpython as bdk
from bitcoin_safe_lib.util import network_kind
from btclib.b32 import p2wpkh
from btclib.b58 import p2pkh, p2wpkh_p2sh
from btclib.bms import sign
from btclib.key import PrvKeyData, PubKeyData
from hwilib.descriptor import parse_descriptor

from .address_types import (
    AddressType,
    AddressTypes,
    DescriptorInfo,
    get_all_address_types,
)
from .device import BaseDevice
from .seed_tools import derive

logger = logging.getLogger(__name__)

_BTCLIB_NETWORK_NAMES: dict[bdk.Network, str] = {
    bdk.Network.BITCOIN: "mainnet",
    bdk.Network.TESTNET: "testnet",
    bdk.Network.TESTNET4: "testnet4",
    bdk.Network.SIGNET: "signet",
    bdk.Network.REGTEST: "regtest",
}

_PURPOSE_TO_ADDRESS_TYPE: dict[int, AddressType] = {
    44: AddressTypes.p2pkh,
    49: AddressTypes.p2sh_p2wpkh,
    84: AddressTypes.p2wpkh,
}


def _address_type_from_bip32_path(bip32_path: str) -> AddressType | None:
    """Return the single-sig address type from the BIP32 purpose level, e.g. m/84h/1h/0h/0/0.

    Returns None for paths without a recognized single-sig purpose (e.g. BIP48 multisig).
    """
    levels = [level for level in bip32_path.split("/") if level and level != "m"]
    if not levels:
        return None
    purpose = int(levels[0].rstrip("'hH"))
    return _PURPOSE_TO_ADDRESS_TYPE.get(purpose)


def _message_address_for(pub_key: PubKeyData, bip32_path: str) -> str:
    """Return the address that selects the message-signature format for the key at bip32_path.

    Unrecognized purposes fall back to the legacy compressed P2PKH format. The signature then
    proves possession of this individual key only, not control of any multisig address.
    """
    address_type = _address_type_from_bip32_path(bip32_path)
    if address_type == AddressTypes.p2sh_p2wpkh:
        return p2wpkh_p2sh(pub_key)
    if address_type == AddressTypes.p2wpkh:
        return p2wpkh(pub_key)
    return p2pkh(pub_key)


class SoftwareSigner(BaseDevice):
    def __init__(
        self,
        mnemonic: str,
        receive_descriptor: str,
        change_descriptor: str,
        network: bdk.Network,
    ) -> None:
        super().__init__(network=network)
        self.mnemonic = mnemonic

        self.descriptors = [
            self._bdk_descriptor_with_secrets(
                descriptor_public=receive_descriptor,
                mnemonic_str=mnemonic,
                network=network,
            ),
            self._bdk_descriptor_with_secrets(
                descriptor_public=change_descriptor,
                mnemonic_str=mnemonic,
                network=network,
            ),
        ]

    def derive(self, key_origin: str):
        xpub, fingerprint = derive(self.mnemonic, key_origin, self.network)
        return xpub

    def get_fingerprint(self) -> str:
        # it doesn't mattrer which AddressTypes i choose, because the fingerprint is identical for all
        address_type = AddressTypes.p2wsh
        xpub, fingerprint = derive(self.mnemonic, address_type.key_origin(self.network), self.network)
        return fingerprint

    def get_xpubs(self, account_index: int = 0) -> dict[AddressType, str]:
        xpubs = {}
        for address_type in get_all_address_types():
            xpub, fingerprint = derive(
                self.mnemonic, address_type.key_origin(self.network, account_index), self.network
            )
            xpubs[address_type] = xpub
        return xpubs

    @classmethod
    def _bdk_descriptor_with_secrets(
        cls,
        mnemonic_str: str,
        descriptor_public: str,
        network: bdk.Network,
    ) -> bdk.Descriptor:
        """
        Uses the mnemonic to create a descriptor with secrets from a descriptor without secrets

        This string replacements necessary, because bdk hasnt got a multisig Descriptor template yet,
        which would allow reconstructing the descriptor from a seed.
        See: https://github.com/bitcoindevkit/bdk-ffi/issues/745

        Returns:
            bdk.Descriptor: _description_
        """

        def strip_derivation_path(s: str) -> str:
            return s[:-2] if s.endswith("/*") else s

        mnemonic = bdk.Mnemonic.from_string(mnemonic_str)
        root_secret_key = bdk.DescriptorSecretKey(network_kind(network), mnemonic, "")
        info = DescriptorInfo.from_str(descriptor_public)

        # bdk works with hardened_char="'" by default and we need to ensure descriptor_with_secret then also has hardened_char="'"
        # descriptor_with_secret: "wpkh([7c85f2b5/84'/1'/0']tpub..../0/*)"
        descriptor_with_secret = parse_descriptor(descriptor_public).to_string_no_checksum(hardened_char="'")
        for spk_provider in info.spk_providers:
            # derived_secret = "[7c85f2b5/84'/1'/0']tpriv..../*"
            derived_secret = root_secret_key.derive(bdk.DerivationPath(spk_provider.key_origin))
            # derived_pub_str = "[7c85f2b5/84'/1'/0']tpub...."
            derived_pub_str = strip_derivation_path(str(derived_secret.as_public()))
            if spk_provider.xpub in derived_pub_str:
                # descriptor_with_secret = "wpkh([7c85f2b5/84'/1'/0']tpriv..../0/*)"
                descriptor_with_secret = descriptor_with_secret.replace(
                    derived_pub_str, strip_derivation_path(str(derived_secret))
                )

        return bdk.Descriptor(descriptor=descriptor_with_secret, network_kind=network_kind(network))

    def sign_psbt(self, psbt: bdk.Psbt) -> bdk.Psbt | None:
        try:
            result = psbt.sign(self.descriptors)
        except bdk.PsbtSignError.NoSecretKeys:
            return None
        if result.errors:
            raise cast(Exception, next(iter(result.errors.values())))
        if not result.signed_inputs:
            return None
        return psbt.finalize().psbt

    def sign_message(self, message: str, bip32_path: str) -> str:
        """Sign a message with the private key at the given BIP32 path.

        The key is derived from the path regardless of its purpose. The message format depends on
        the purpose:
        - BIP44: legacy P2PKH signature (BIP137 header 31-34)
        - BIP49: nested SegWit P2SH-P2WPKH BIP137 signature (header 35-38)
        - BIP84: native SegWit P2WPKH BIP137 signature (header 39-42)
        - any other valid path, e.g. BIP48 multisig: legacy compressed P2PKH signature (header 31-34)

        For multisig paths (e.g. m/48h/1h/0h/2h/0/4) the signature proves possession of the individual
        cosigner's key, NOT control of the multisig address. No BIP322 multisig message signing is
        provided.

        Returns the base64 encoded 65 byte compact recoverable signature.
        """
        mnemonic = bdk.Mnemonic.from_string(self.mnemonic)
        root_secret_key = bdk.DescriptorSecretKey(network_kind(self.network), mnemonic, "")
        derived_secret = root_secret_key.derive(bdk.DerivationPath(bip32_path))
        secret = bytes(derived_secret.secret_bytes())

        btclib_network = _BTCLIB_NETWORK_NAMES[self.network]
        prv_key = PrvKeyData(int.from_bytes(secret, "big"), btclib_network, compressed=True)
        address = _message_address_for(prv_key.pub, bip32_path)

        # the address selects the BIP137 header range: P2PKH 31-34, P2SH-P2WPKH 35-38, P2WPKH 39-42
        signature = sign(message.encode("utf-8").hex(), prv_key, address)
        return signature.b64encode()

    def display_address(
        self,
        address_descriptor: str,
    ) -> str:
        raise NotImplementedError()
