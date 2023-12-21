import logging

logger = logging.getLogger(__name__)

import bdkpython as bdk
from typing import Callable, Dict, List, Tuple

from hwilib.descriptor import (
    parse_descriptor,
    Descriptor,
    PubkeyProvider,
    WPKHDescriptor,
    WSHDescriptor,
    PKHDescriptor,
    MultisigDescriptor,
    TRDescriptor,
    SHDescriptor,
)
from hwilib.key import KeyOriginInfo, HARDENED_FLAG
from hwilib.common import AddressType as HWIAddressType


# https://bitcoin.design/guide/glossary/address/
# https://learnmeabitcoin.com/technical/derivation-paths
# https://github.com/bitcoin/bips/blob/master/bip-0380.mediawiki
class AddressType:
    def __init__(
        self,
        name,
        is_multisig,
        key_origin=None,
        bdk_descriptor_secret=None,
        hwi_descriptor_classes=None,
        info_url=None,
        description=None,
        bdk_descriptor=None,
    ) -> None:
        self.name = name
        self.is_multisig = is_multisig
        self.key_origin: Callable = key_origin
        self.bdk_descriptor_secret = bdk_descriptor_secret
        self.info_url = info_url
        self.description = description
        self.bdk_descriptor = bdk_descriptor
        self.hwi_descriptor_classes = hwi_descriptor_classes

    def clone(self):
        return AddressType(
            name=self.name,
            is_multisig=self.is_multisig,
            key_origin=self.key_origin,
            bdk_descriptor_secret=self.bdk_descriptor_secret,
            info_url=self.info_url,
            description=self.description,
            bdk_descriptor=self.bdk_descriptor,
            hwi_descriptor_classes=self.hwi_descriptor_classes,
        )

    def __str__(self):
        return str(self.name)

    def __repr__(self):
        return f"AddressType({self.__dict__})"

    def get_bip32_path(
        self, network: bdk.Network, keychain: bdk.KeychainKind, address_index: int
    ) -> str:
        return f"{self.key_origin(network)}/{0 if keychain == bdk.KeychainKind.EXTERNAL else 1}/{address_index}"


class AddressTypes:
    p2pkh = AddressType(
        "Single Sig (Legacy/p2pkh)",
        False,
        key_origin=lambda network: f"m/44h/{0 if network==bdk.Network.BITCOIN else 1}h/0h",
        bdk_descriptor=bdk.Descriptor.new_bip44_public,
        bdk_descriptor_secret=bdk.Descriptor.new_bip44,
        info_url="https://learnmeabitcoin.com/technical/derivation-paths",
        description="Legacy (single sig) addresses that look like 1addresses",
        hwi_descriptor_classes=(PKHDescriptor,),
    )
    p2sh_p2wpkh = AddressType(
        "Single Sig (Nested/p2sh-p2wpkh)",
        False,
        key_origin=lambda network: f"m/49h/{0 if network==bdk.Network.BITCOIN else 1}h/0h",
        bdk_descriptor=bdk.Descriptor.new_bip49_public,
        bdk_descriptor_secret=bdk.Descriptor.new_bip49,
        info_url="https://learnmeabitcoin.com/technical/derivation-paths",
        description="Nested (single sig) addresses that look like 3addresses",
        hwi_descriptor_classes=(SHDescriptor, WPKHDescriptor),
    )
    p2wpkh = AddressType(
        "Single Sig (SegWit/p2wpkh)",
        False,
        key_origin=lambda network: f"m/84h/{0 if network==bdk.Network.BITCOIN else 1}h/0h",
        bdk_descriptor=bdk.Descriptor.new_bip84_public,
        bdk_descriptor_secret=bdk.Descriptor.new_bip84,
        info_url="https://learnmeabitcoin.com/technical/derivation-paths",
        description="SegWit (single sig) addresses that look like bc1addresses",
        hwi_descriptor_classes=(WPKHDescriptor,),
    )
    p2tr = AddressType(
        "Single Sig (Taproot/p2tr)",
        False,
        key_origin=lambda network: f"m/86h/{0 if network==bdk.Network.BITCOIN else 1}h/0h",
        bdk_descriptor=bdk.Descriptor.new_bip86_public,
        bdk_descriptor_secret=bdk.Descriptor.new_bip86,
        info_url="https://github.com/bitcoin/bips/blob/master/bip-0386.mediawiki",
        description="Taproot (single sig) addresses ",
        hwi_descriptor_classes=(TRDescriptor,),
    )
    p2sh_p2wsh = AddressType(
        "Multi Sig (Nested/p2sh-p2wsh)",
        True,
        key_origin=lambda network: f"m/48h/{0 if network==bdk.Network.BITCOIN else 1}h/0h/1h",
        bdk_descriptor_secret=None,
        info_url="https://github.com/bitcoin/bips/blob/master/bip-0048.mediawiki",
        description="Nested (multi sig) addresses that look like 3addresses",
        hwi_descriptor_classes=(SHDescriptor, WSHDescriptor, MultisigDescriptor),
    )
    p2wsh = AddressType(
        "Multi Sig (SegWit/p2wsh)",
        True,
        key_origin=lambda network: f"m/48h/{0 if network==bdk.Network.BITCOIN else 1}h/0h/2h",
        bdk_descriptor_secret=None,
        info_url="https://github.com/bitcoin/bips/blob/master/bip-0048.mediawiki",
        description="SegWit (multi sig) addresses that look like bc1addresses",
        hwi_descriptor_classes=(WSHDescriptor, MultisigDescriptor),
    )


def get_address_type_dicts() -> Dict[str, AddressType]:
    return {k: v for k, v in AddressTypes.__dict__.items() if (not k.startswith("_"))}


def get_address_types() -> List[AddressType]:
    return get_address_type_dicts().values()


def get_hwi_address_type(address_type: AddressType) -> HWIAddressType:
    # see https://hwi.readthedocs.io/en/latest/usage/api-usage.html#hwilib.common.AddressType
    if address_type.name in [AddressTypes.p2pkh.name]:
        return HWIAddressType.LEGACY
    if address_type.name in [AddressTypes.p2wpkh.name]:
        return HWIAddressType.WIT
    if address_type.name in [
        AddressTypes.p2sh_p2wpkh.name,
        AddressTypes.p2sh_p2wsh.name,
    ]:
        return HWIAddressType.SH_WIT
    if address_type.name in [AddressTypes.p2tr.name]:
        return HWIAddressType.TAP


class SignerInfo:
    def __init__(
        self,
        xpub: str,
        fingerprint: str,
        key_origin: str,
        derivation_path: str,
    ) -> None:
        self.xpub = xpub
        self.fingerprint = fingerprint
        # key_origin example: "m/84h/1h/0h"
        assert key_origin.startswith("m/")
        self.key_origin = key_origin
        # derivation_path example "/0/*"
        assert derivation_path.startswith("/")
        self.derivation_path = derivation_path

    @classmethod
    def from_hwi(pubkey_provider: PubkeyProvider) -> "SignerInfo":
        return SignerInfo(
            xpub=pubkey_provider.pubkey,
            fingerprint=pubkey_provider.origin.fingerprint.hex(),
            key_origin=pubkey_provider.origin.get_derivation_path(),
            derivation_path=pubkey_provider.deriv_path,
        )

    def to_hwi_pubkey_provider(self) -> PubkeyProvider:
        hwi_key_origin = self.key_origin.replace("m/", f"{self.fingerprint}/")
        provider = PubkeyProvider(
            origin=hwi_key_origin, pubkey=self.xpub, deriv_path=self.derivation_path
        )
        return provider


def _get_descriptor_instances(descriptor):
    "Returns the linear chain of chained descriptors . Multiple subdescriptors return an error"
    assert len(descriptor.subdescriptors) <= 1
    if descriptor.subdescriptors:
        result = [descriptor]
        for subdescriptor in descriptor.subdescriptors:
            result += _get_descriptor_instances(subdescriptor)
        return result
    else:
        return [descriptor]


def _find_matching_address_type(instance_tuple, address_types: List[AddressType]):
    for address_type in address_types:
        if len(instance_tuple) == len(address_type.hwi_descriptor_classes) and all(
            isinstance(i, c)
            for i, c in zip(instance_tuple, address_type.hwi_descriptor_classes)
        ):
            return address_type
    return None


class DescriptorInfo:
    def __init__(
        self, address_type: AddressType, signer_infos: List[SignerInfo], threshold=1
    ) -> None:
        self.address_type = address_type
        self.signer_infos = signer_infos
        self.threshold = threshold


def public_descriptor_info(descriptor_str: str) -> DescriptorInfo:
    "gets the xpub (not xpriv) information"

    hwi_descriptor = parse_descriptor(descriptor_str)

    # first we need to identify the address type
    address_type = _find_matching_address_type(
        _get_descriptor_instances(hwi_descriptor), get_address_types()
    )
    if not address_type:
        raise ValueError(
            f"descriptor {descriptor_str} cannot be matched to known template"
        )

    # get the     pubkey_providers, by "walking to the end of desciptors"
    threshold = 1
    subdescriptor = hwi_descriptor
    for descritptor_class in address_type.hwi_descriptor_classes:
        # just double checking that _find_matching_address_type did its job correctly
        assert isinstance(subdescriptor, descritptor_class)
        subdescriptor = subdescriptor.subdescriptors[0]

        if descritptor_class == MultisigDescriptor:
            # last descriptor is a multisig
            threshold = subdescriptor.thresh

    pubkey_providers = subdescriptor.pubkeys

    return DescriptorInfo(
        address_type=address_type,
        signer_infos=[
            SignerInfo.from_hwi(pubkey_provider) for pubkey_provider in pubkey_providers
        ],
        threshold=threshold,
    )


def make_multisig_descriptor(
    address_type: AddressType, threshold: int, descriptors: List[bdk.Descriptor]
) -> bdk.Descriptor:
    "Takes in single sig descriptors and creates a multisig descritpr out of it"

    assert address_type.is_multisig
    assert descriptors

    # check all descriptors have the same network
    assert all(
        [descriptor.network == descriptors[0].network for descriptor in descriptors]
    ), "Descriptors with different networks given"

    hwi_pubkey_providers = []
    for descriptor in descriptors:
        hwi_pubkey_provider = _descriptor_to_hwi_pubkey_providers(
            descriptor.as_string_private()
        )
        if not hwi_pubkey_provider or len(hwi_pubkey_provider) >= 2:
            # cannot handle. The argument descriptors are only singlesig descriptors
            return
        hwi_pubkey_providers.append(hwi_pubkey_provider[0])

    multisig_hwi_descriptor = address_type.hwi_descriptor_classes(
        pubkeys=hwi_pubkey_providers, thresh=threshold, is_sorted=True
    )

    return bdk.Descriptor(
        multisig_hwi_descriptor.to_string(), network=descriptors[0].network
    )
