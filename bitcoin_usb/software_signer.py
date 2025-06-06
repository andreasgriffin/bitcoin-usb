import logging
from typing import Dict

import bdkpython as bdk
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
                descriptor_public=receive_descriptor, mnemonic_str=mnemonic, network=network
            ),
            change_descriptor=self._bdk_descriptor_with_secrets(
                descriptor_public=change_descriptor, mnemonic_str=mnemonic, network=network
            ),
            network=self.network,
            connection=bdk.Connection.new_in_memory(),
        )

    def derive(self, key_origin: str):
        xpub, fingerprint = derive(self.mnemonic, key_origin, self.network)
        return xpub

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
        root_secret_key = bdk.DescriptorSecretKey(network, mnemonic, "")
        info = DescriptorInfo.from_str(descriptor_public)

        # bdk works with hardened_char="'" by default and we need to ensure descriptor_with_secret then also has hardened_char="'"
        # descriptor_with_secret: "wpkh([7c85f2b5/84'/1'/0']tpub..../0/*)"
        descriptor_with_secret = parse_descriptor(descriptor_public).to_string_no_checksum(hardened_char="'")
        for spk_provider in info.spk_providers:
            # derived_secret = "[7c85f2b5/84'/1'/0']tpriv..../*"
            derived_secret = root_secret_key.derive(bdk.DerivationPath(spk_provider.key_origin))
            # derived_pub_str = "[7c85f2b5/84'/1'/0']tpub...."
            derived_pub_str = strip_derivation_path(derived_secret.as_public().as_string())
            if spk_provider.xpub in derived_pub_str:
                # descriptor_with_secret = "wpkh([7c85f2b5/84'/1'/0']tpriv..../0/*)"
                descriptor_with_secret = descriptor_with_secret.replace(
                    derived_pub_str, strip_derivation_path(derived_secret.as_string())
                )

        return bdk.Descriptor(descriptor=descriptor_with_secret, network=network)

    def sign_psbt(self, input_psbt: bdk.Psbt) -> bdk.Psbt | None:

        previous_serialized = input_psbt.serialize()
        fully_signed = self.wallet.sign(psbt=input_psbt, sign_options=None)
        if fully_signed:
            return input_psbt
        if input_psbt.serialize() == previous_serialized:
            return None
        return input_psbt

    def sign_message(self, message: str, bip32_path: str) -> str:
        raise NotImplementedError("")

    def display_address(
        self,
        address_descriptor: str,
    ):
        pass
