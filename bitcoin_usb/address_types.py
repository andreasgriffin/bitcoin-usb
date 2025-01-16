import logging

from bitcoin_usb.i18n import translate

logger = logging.getLogger(__name__)

from typing import Callable, Dict, List, Optional, Sequence, Type

import bdkpython as bdk
from hwilib.common import AddressType as HWIAddressType
from hwilib.descriptor import (
    Descriptor,
    MultisigDescriptor,
    PKHDescriptor,
    PubkeyProvider,
    SHDescriptor,
    TRDescriptor,
    WPKHDescriptor,
    WSHDescriptor,
    parse_descriptor,
)
from hwilib.key import KeyOriginInfo


class ConstDerivationPaths:
    receive = "/0/*"
    change = "/1/*"
    multipath = "/<0;1>/*"


# https://bitcoin.design/guide/glossary/address/
# https://learnmeabitcoin.com/technical/derivation-paths
# https://github.com/bitcoin/bips/blob/master/bip-0380.mediawiki
class AddressType:
    def __init__(
        self,
        short_name: str,
        name: str,
        is_multisig: bool,
        hwi_descriptor_classes: Sequence[Type[Descriptor]],
        key_origin: Callable[[bdk.Network], str],
        bdk_descriptor_secret: Callable[
            [bdk.DescriptorSecretKey, bdk.KeychainKind, bdk.Network], bdk.Descriptor
        ]
        | None = None,
        info_url: str | None = None,
        description: str | None = None,
        bdk_descriptor: Callable[
            [bdk.DescriptorPublicKey, str, bdk.KeychainKind, bdk.Network], bdk.Descriptor
        ]
        | None = None,
    ) -> None:
        self.short_name = short_name
        self.name = name
        self.is_multisig = is_multisig
        self.key_origin: Callable[[bdk.Network], str] = key_origin
        self.bdk_descriptor_secret = bdk_descriptor_secret
        self.info_url = info_url
        self.description = description
        self.bdk_descriptor = bdk_descriptor
        self.hwi_descriptor_classes = hwi_descriptor_classes

    def clone(self):
        return AddressType(
            short_name=self.short_name,
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

    def get_bip32_path(self, network: bdk.Network, keychain: bdk.KeychainKind, address_index: int) -> str:
        return f"m/{0 if keychain == bdk.KeychainKind.EXTERNAL else 1}/{address_index}"


class AddressTypes:
    p2pkh = AddressType(
        "p2pkh",
        "Single Sig (Legacy/p2pkh)",
        is_multisig=False,
        key_origin=lambda network: f"m/44h/{0 if network==bdk.Network.BITCOIN else 1}h/0h",
        bdk_descriptor=bdk.Descriptor.new_bip44_public,
        bdk_descriptor_secret=bdk.Descriptor.new_bip44,
        info_url="https://learnmeabitcoin.com/technical/derivation-paths",
        description="Legacy (single sig) addresses that look like 1addresses",
        hwi_descriptor_classes=(PKHDescriptor,),
    )
    p2sh_p2wpkh = AddressType(
        "p2sh-p2wpkh",
        "Single Sig (Nested/p2sh-p2wpkh)",
        is_multisig=False,
        key_origin=lambda network: f"m/49h/{0 if network==bdk.Network.BITCOIN else 1}h/0h",
        bdk_descriptor=bdk.Descriptor.new_bip49_public,
        bdk_descriptor_secret=bdk.Descriptor.new_bip49,
        info_url="https://learnmeabitcoin.com/technical/derivation-paths",
        description="Nested (single sig) addresses that look like 3addresses",
        hwi_descriptor_classes=(SHDescriptor, WPKHDescriptor),
    )
    p2wpkh = AddressType(
        "p2wpkh",
        "Single Sig (SegWit/p2wpkh)",
        is_multisig=False,
        key_origin=lambda network: f"m/84h/{0 if network==bdk.Network.BITCOIN else 1}h/0h",
        bdk_descriptor=bdk.Descriptor.new_bip84_public,
        bdk_descriptor_secret=bdk.Descriptor.new_bip84,
        info_url="https://learnmeabitcoin.com/technical/derivation-paths",
        description="SegWit (single sig) addresses that look like bc1addresses",
        hwi_descriptor_classes=(WPKHDescriptor,),
    )
    p2tr = AddressType(
        "p2tr",
        "Single Sig (Taproot/p2tr)",
        is_multisig=False,
        key_origin=lambda network: f"m/86h/{0 if network==bdk.Network.BITCOIN else 1}h/0h",
        bdk_descriptor=bdk.Descriptor.new_bip86_public,
        bdk_descriptor_secret=bdk.Descriptor.new_bip86,
        info_url="https://github.com/bitcoin/bips/blob/master/bip-0386.mediawiki",
        description="Taproot (single sig) addresses ",
        hwi_descriptor_classes=(TRDescriptor,),
    )
    p2sh_p2wsh = AddressType(
        "p2sh-p2wsh",
        "Multi Sig (Nested/p2sh-p2wsh)",
        is_multisig=True,
        key_origin=lambda network: f"m/48h/{0 if network==bdk.Network.BITCOIN else 1}h/0h/1h",
        bdk_descriptor_secret=None,
        info_url="https://github.com/bitcoin/bips/blob/master/bip-0048.mediawiki",
        description="Nested (multi sig) addresses that look like 3addresses",
        hwi_descriptor_classes=(SHDescriptor, WSHDescriptor, MultisigDescriptor),
    )
    p2wsh = AddressType(
        "p2wsh",
        "Multi Sig (SegWit/p2wsh)",
        is_multisig=True,
        key_origin=lambda network: f"m/48h/{0 if network==bdk.Network.BITCOIN else 1}h/0h/2h",
        bdk_descriptor_secret=None,
        info_url="https://github.com/bitcoin/bips/blob/master/bip-0048.mediawiki",
        description="SegWit (multi sig) addresses that look like bc1addresses",
        hwi_descriptor_classes=(WSHDescriptor, MultisigDescriptor),
    )


def get_address_type_dicts() -> Dict[str, AddressType]:
    return {k: v for k, v in AddressTypes.__dict__.items() if (not k.startswith("_"))}


def get_all_address_types() -> List[AddressType]:
    return list(get_address_type_dicts().values())


def get_address_types(is_multisig: bool) -> List[AddressType]:
    return [a for a in get_all_address_types() if a.is_multisig == is_multisig]


def get_hwi_address_type(address_type: AddressType) -> HWIAddressType:
    # see https://hwi.readthedocs.io/en/latest/usage/api-usage.html#hwilib.common.AddressType
    if address_type.name in [AddressTypes.p2pkh.name]:
        return HWIAddressType.LEGACY
    if address_type.name in [AddressTypes.p2wpkh.name, AddressTypes.p2wsh.name]:
        return HWIAddressType.WIT
    if address_type.name in [
        AddressTypes.p2sh_p2wpkh.name,
        AddressTypes.p2sh_p2wsh.name,
    ]:
        return HWIAddressType.SH_WIT
    if address_type.name in [AddressTypes.p2tr.name]:
        return HWIAddressType.TAP

    raise ValueError(
        translate("bitcoin_usb", "No HWI AddressType could be found for {name}").format(
            name=address_type.name
        )
    )


class SimplePubKeyProvider:
    def __init__(
        self,
        xpub: str,
        fingerprint: str,
        key_origin: str,
        derivation_path: str = ConstDerivationPaths.receive,
    ) -> None:
        self.xpub = xpub.strip()
        self.fingerprint = self.format_fingerprint(fingerprint)
        # key_origin example: "m/84h/1h/0h"
        self.key_origin = self.format_key_origin(key_origin)
        # derivation_path example "/0/*"
        self.derivation_path = self.format_derivation_path(derivation_path)

    @classmethod
    def format_derivation_path(cls, value: str) -> str:
        value = value.replace(" ", "").strip()
        if not value.startswith("/"):
            raise ValueError(
                translate("bitcoin_usb", "derivation_path {value} must start with a /").format(value=value)
            )
        return value.replace("'", "h")

    @classmethod
    def format_key_origin(cls, value: str) -> str:
        def filter_characters(s):
            allowed_chars = set("m/'h0123456789")
            filtered_string = "".join(c for c in s if c in allowed_chars)
            return filtered_string

        value = filter_characters(value.replace("'", "h").strip())
        if value == "m":
            # handle the special case that the key is the highest key without derivation
            return value

        for group in value.split("/"):
            if group.count("h") > 1:
                raise ValueError(translate("bitcoin_usb", "h cannot appear twice in a index"))

        if not value.startswith("m/"):
            raise ValueError(translate("bitcoin_usb", "{value} must start with m/").format(value=value))
        if "//" in value:
            raise ValueError(translate("bitcoin_usb", "{value} cannot contain //").format(value=value))
        if "/h" in value:
            raise ValueError(translate("bitcoin_usb", "{value} cannot contain /h").format(value=value))
        if "hh" in value:
            raise ValueError(translate("bitcoin_usb", "{value} cannot contain hh").format(value=value))
        if value.endswith("/"):
            raise ValueError(translate("bitcoin_usb", "{value} cannot end with /").format(value=value))
        return value

    @classmethod
    def is_fingerprint_valid(cls, fingerprint: str):
        try:
            int(fingerprint, 16)
            return len(fingerprint) == 8
        except ValueError:
            return False

    @classmethod
    def format_fingerprint(cls, value: str) -> str:
        value = value.replace(" ", "").strip()
        if not cls.is_fingerprint_valid(value):
            raise ValueError(
                translate("bitcoin_usb", "{value} is not a valid fingerprint").format(value=value)
            )
        return value.upper()

    def clone(self) -> "SimplePubKeyProvider":
        return SimplePubKeyProvider(self.xpub, self.fingerprint, self.key_origin, self.derivation_path)

    def is_testnet(self):
        network_str = self.key_origin.split("/")[2]
        if not network_str.endswith("h"):
            raise ValueError(
                translate(
                    "bitcoin_usb",
                    "The network part {network_str} of the key origin {key_origin} must be hardened with a h",
                ).format(network_str=network_str, key_origin=self.key_origin)
            )
        network_index = int(network_str.replace("h", ""))
        if network_index == 0:
            return False
        elif network_index == 1:
            return True
        else:
            # https://learnmeabitcoin.com/technical/derivation-paths
            raise ValueError(
                translate("bitcoin_usb", "Unknown network/coin type {network_str} in {key_origin}").format(
                    network_str=network_str, key_origin=self.key_origin
                )
            )

    @classmethod
    def from_hwi(cls, pubkey_provider: PubkeyProvider) -> "SimplePubKeyProvider":
        return SimplePubKeyProvider(
            xpub=pubkey_provider.pubkey,
            fingerprint=pubkey_provider.origin.fingerprint.hex(),
            key_origin=pubkey_provider.origin.get_derivation_path(),
            derivation_path=pubkey_provider.deriv_path,
        )

    def to_hwi_pubkey_provider(self) -> PubkeyProvider:

        provider = PubkeyProvider(
            origin=KeyOriginInfo.from_string(self.key_origin.replace("m", f"{self.fingerprint}")),
            pubkey=self.xpub,
            deriv_path=self.derivation_path,
        )
        return provider

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__dict__})"


def _get_descriptor_instances(descriptor: Descriptor) -> List[Descriptor]:
    "Returns the linear chain of chained descriptors . Multiple subdescriptors return an error"
    assert len(descriptor.subdescriptors) <= 1
    if descriptor.subdescriptors:
        result = [descriptor]
        for subdescriptor in descriptor.subdescriptors:
            result += _get_descriptor_instances(subdescriptor)
        return result
    else:
        return [descriptor]


def _find_matching_address_type(
    descriptor_tuple: List[Descriptor], address_types: List[AddressType]
) -> Optional[AddressType]:
    for address_type in address_types:
        if len(descriptor_tuple) == len(address_type.hwi_descriptor_classes) and all(
            isinstance(i, c) for i, c in zip(descriptor_tuple, address_type.hwi_descriptor_classes)
        ):
            return address_type
    return None


class DescriptorInfo:
    def __init__(
        self,
        address_type: AddressType,
        spk_providers: List[SimplePubKeyProvider],
        threshold=1,
    ) -> None:
        self.address_type: AddressType = address_type
        self.spk_providers: List[SimplePubKeyProvider] = spk_providers
        self.threshold: int = threshold

        if not self.address_type.is_multisig:
            assert len(spk_providers) <= 1

    def __repr__(self) -> str:
        return f"{self.__dict__}"

    def get_hwi_descriptor(self, network: bdk.Network):
        # check that the key_origins of the spk_providers are matching the desired output address_type
        for spk_provider in self.spk_providers:
            if spk_provider.key_origin != self.address_type.key_origin(network):
                logger.warning(
                    f"{spk_provider.key_origin} does not match the default key origin {self.address_type.key_origin(network)} for this address type {self.address_type.name}!"
                )

        if self.address_type.is_multisig:
            assert self.address_type.hwi_descriptor_classes[-1] == MultisigDescriptor
            hwi_descriptor = MultisigDescriptor(
                pubkeys=[provider.to_hwi_pubkey_provider() for provider in self.spk_providers],
                thresh=self.threshold,
                is_sorted=True,
            )
        else:
            hwi_descriptor = self.address_type.hwi_descriptor_classes[-1](
                self.spk_providers[0].to_hwi_pubkey_provider()
            )

        for hwi_descriptor_class in reversed(self.address_type.hwi_descriptor_classes[:-1]):
            hwi_descriptor = hwi_descriptor_class(hwi_descriptor)

        return hwi_descriptor

    def get_bdk_descriptor(self, network: bdk.Network):
        return bdk.Descriptor(self.get_hwi_descriptor(network).to_string(), network=network)

    @classmethod
    def from_str(cls, descriptor_str: str) -> "DescriptorInfo":
        hwi_descriptor = parse_descriptor(descriptor_str)

        # first we need to identify the address type
        address_type = _find_matching_address_type(
            _get_descriptor_instances(hwi_descriptor), get_all_address_types()
        )
        if not address_type:
            supported_types = [address_type.short_name for address_type in get_all_address_types()]
            raise ValueError(
                f"descriptor {descriptor_str} cannot be matched to a supported template. Supported templates are {supported_types}"
            )

        # get the     pubkey_providers, by "walking to the end of desciptors"
        threshold = 1
        subdescriptor = hwi_descriptor
        for descritptor_class in address_type.hwi_descriptor_classes:
            # just double checking that _find_matching_address_type did its job correctly
            assert isinstance(subdescriptor, descritptor_class)
            subdescriptor = subdescriptor.subdescriptors[0] if subdescriptor.subdescriptors else subdescriptor

        pubkey_providers = subdescriptor.pubkeys
        if isinstance(subdescriptor, MultisigDescriptor):
            # last descriptor is a multisig
            threshold = subdescriptor.thresh

        return DescriptorInfo(
            address_type=address_type,
            spk_providers=[
                SimplePubKeyProvider.from_hwi(pubkey_provider) for pubkey_provider in pubkey_providers
            ],
            threshold=threshold,
        )
