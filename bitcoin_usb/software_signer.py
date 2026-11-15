import logging

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


def _address_type_from_bip32_path(bip32_path: str) -> AddressType:
    """Return the single-sig address type from the BIP32 purpose level, e.g. m/84h/1h/0h/0/0."""
    levels = [level for level in bip32_path.split("/") if level and level != "m"]
    purpose = int(levels[0].rstrip("'hH"))
    address_type = _PURPOSE_TO_ADDRESS_TYPE.get(purpose)
    if address_type is None:
        raise ValueError(f"Unsupported purpose for message signing: {bip32_path}")
    return address_type


def _address_for(pub_key: PubKeyData, address_type: AddressType) -> str:
    if address_type == AddressTypes.p2pkh:
        return p2pkh(pub_key)
    if address_type == AddressTypes.p2sh_p2wpkh:
        return p2wpkh_p2sh(pub_key)
    return p2wpkh(pub_key)


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

        self.wallet = bdk.Wallet(
            descriptor=self._bdk_descriptor_with_secrets(
                descriptor_public=receive_descriptor,
                mnemonic_str=mnemonic,
                network=network,
            ),
            change_descriptor=self._bdk_descriptor_with_secrets(
                descriptor_public=change_descriptor,
                mnemonic_str=mnemonic,
                network=network,
            ),
            network=self.network,
            persister=bdk.Persister.new_in_memory(),
        )

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
        previous_serialized = psbt.serialize()
        fully_signed = self.wallet.sign(psbt=psbt, sign_options=None)
        if fully_signed:
            return psbt
        if psbt.serialize() == previous_serialized:
            return None
        return psbt

    def sign_message(self, message: str, bip32_path: str) -> str:
        """Sign a BIP137 message with the key at bip32_path.

        Returns the base64 encoded 65 byte compact recoverable signature, in the same
        format the hardware devices return.
        """
        mnemonic = bdk.Mnemonic.from_string(self.mnemonic)
        root_secret_key = bdk.DescriptorSecretKey(network_kind(self.network), mnemonic, "")
        derived_secret = root_secret_key.derive(bdk.DerivationPath(bip32_path))
        secret = bytes(derived_secret.secret_bytes())

        btclib_network = _BTCLIB_NETWORK_NAMES[self.network]
        prv_key = PrvKeyData(int.from_bytes(secret, "big"), btclib_network, compressed=True)
        address = _address_for(prv_key.pub, _address_type_from_bip32_path(bip32_path))

        # the address selects the BIP137 header range: P2PKH 31-34, P2SH-P2WPKH 35-38, P2WPKH 39-42
        signature = sign(message.encode("utf-8").hex(), prv_key, address)
        return signature.b64encode()

    def display_address(
        self,
        address_descriptor: str,
    ) -> str:
        raise NotImplementedError()
