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
from hwilib.key import (
    HARDENED_FLAG,
    ExtendedKey,
    KeyOriginInfo,
    is_hardened,
    parse_path,
)


class SortedMultisigDescriptor(MultisigDescriptor):
    def __init__(self, pubkeys: List[PubkeyProvider], thresh: int) -> None:
        super().__init__(pubkeys, thresh, True)

    @classmethod
    def is_sorted_multisig(cls, descriptor: Descriptor) -> bool:
        return isinstance(descriptor, MultisigDescriptor) and descriptor.is_sorted

    @classmethod
    def from_multisig_descriptor(cls, descriptor: Descriptor):
        assert isinstance(descriptor, MultisigDescriptor)
        assert descriptor.is_sorted
        return cls(descriptor.pubkeys, descriptor.thresh)


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
        hwi_descriptor_classes=(SHDescriptor, WSHDescriptor, SortedMultisigDescriptor),
    )
    p2wsh = AddressType(
        "p2wsh",
        "Multi Sig (SegWit/p2wsh)",
        is_multisig=True,
        key_origin=lambda network: f"m/48h/{0 if network==bdk.Network.BITCOIN else 1}h/0h/2h",
        bdk_descriptor_secret=None,
        info_url="https://github.com/bitcoin/bips/blob/master/bip-0048.mediawiki",
        description="SegWit (multi sig) addresses that look like bc1addresses",
        hwi_descriptor_classes=(WSHDescriptor, SortedMultisigDescriptor),
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
        xpub = xpub.strip()
        self.xpub = ExtendedKey.deserialize(xpub).to_string()
        if self.xpub != xpub:
            raise ValueError(f"xpub {xpub} changed during deserialize/serialize!")

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
    def format_key_origin(cls, value: str, remove_spaces=True) -> str:
        if remove_spaces:
            value = value.replace(" ", "")
        if value == "m":
            # handle the special case that the key is the highest key without derivation
            return value

        # must pass the hwi parsing test
        indexes = parse_path(value)
        assert indexes, "Could not parse the key origin"

        return cls.key_origin_indexes_to_str(indexes)

    @classmethod
    def robust_parse_path(cls, key_origin: str) -> Optional[List[int]]:
        # normalize the input and ensure it is valid
        try:
            indexes = parse_path(key_origin)
        except:
            return None
        return indexes

    @classmethod
    def get_network_index(cls, key_origin: str) -> Optional[int]:
        # normalize the input and ensure it is valid
        indexes = cls.robust_parse_path(key_origin)
        if not indexes:
            return None

        if len(indexes) < 2:
            logger.warning(f"{key_origin} has too few levels for a network_index")
            return None

        index_network = indexes[1]

        if not is_hardened(index_network):
            logger.warning(f"The network index ({index_network}) must be hardened")
            return None

        return index_network & ~HARDENED_FLAG

    @classmethod
    def get_account_index(cls, key_origin: str) -> Optional[int]:
        # normalize the input and ensure it is valid
        indexes = cls.robust_parse_path(key_origin)
        if not indexes:
            return None

        if len(indexes) < 3:
            logger.warning(f"{key_origin} has too few levels for a account_index")
            return None

        index_network = indexes[2]

        if not is_hardened(index_network):
            logger.warning(f"The account_index ({index_network}) must be hardened")
            return None

        return index_network & ~HARDENED_FLAG

    @classmethod
    def key_origin_indexes_to_str(cls, indexes: List[int]) -> str:
        def _path_string(self, hardened_char: str = "h") -> str:
            s = ""
            for i in indexes:
                hardened = is_hardened(i)
                i &= ~HARDENED_FLAG
                s += "/" + str(i)
                if hardened:
                    s += hardened_char
            return s

        return f"m{_path_string(indexes)}"

    @classmethod
    def key_origin_identical_disregarding_account(
        cls,
        key_origin1: str,
        key_origin2: str,
    ) -> bool:
        indexes2 = cls.robust_parse_path(key_origin2)
        if indexes2 is None:
            return False

        a1, a2 = cls.get_account_index(key_origin1), cls.get_account_index(key_origin2)
        if a1 is None or a2 is None:
            return False

        indexes2_with_a1 = indexes2.copy()
        indexes2_with_a1[2] = a1 | HARDENED_FLAG

        return key_origin1 == cls.key_origin_indexes_to_str(indexes2_with_a1)

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

    def get_address_bip32_path(self, kind: bdk.KeychainKind, index: int):
        return f"{self.key_origin}/{0 if kind == bdk.KeychainKind.EXTERNAL else 1}/{index}"


def _get_descriptor_instances(descriptor: Descriptor) -> List[Descriptor]:
    """
    Returns the linear chain of chained descriptors, and converts MultisigDescriptor into SortedMultisigDescriptor if possible.
    Multiple subdescriptors return an error


    Args:
        descriptor (Descriptor): _description_

    Returns:
        List[Descriptor]: _description_
    """
    assert len(descriptor.subdescriptors) <= 1
    if descriptor.subdescriptors:
        result = [
            SortedMultisigDescriptor.from_multisig_descriptor(descriptor)
            if SortedMultisigDescriptor.is_sorted_multisig(descriptor)
            else descriptor
        ]
        for subdescriptor in descriptor.subdescriptors:
            result += _get_descriptor_instances(subdescriptor)
        return result
    else:
        return [
            SortedMultisigDescriptor.from_multisig_descriptor(descriptor)
            if SortedMultisigDescriptor.is_sorted_multisig(descriptor)
            else descriptor
        ]


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
            assert (
                self.address_type.hwi_descriptor_classes[-1] != MultisigDescriptor
            )  # multi() is not suuported, and may not be added in AddressType
            assert self.address_type.hwi_descriptor_classes[-1] == SortedMultisigDescriptor
            hwi_descriptor = SortedMultisigDescriptor(
                pubkeys=[provider.to_hwi_pubkey_provider() for provider in self.spk_providers],
                thresh=self.threshold,
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
        """
        Requres the descriptor_str to be a nested chain of descriptors, that have at most 1 branch
        If there are more than 1 subdescriptors (branches), it will raise an Exception

        Args:
            descriptor_str (str): _description_

        Raises:
            ValueError: _description_

        Returns:
            DescriptorInfo: _description_
        """
        hwi_descriptor = parse_descriptor(descriptor_str)
        linear_chain_descriptors = _get_descriptor_instances(hwi_descriptor)

        # first we need to identify the address type
        address_type = _find_matching_address_type(linear_chain_descriptors, get_all_address_types())
        if not address_type:
            supported_types = [address_type.short_name for address_type in get_all_address_types()]
            raise ValueError(
                f"descriptor {descriptor_str} cannot be matched to a supported template. Supported templates are {supported_types}"
            )

        # get the     pubkey_providers, by "walking to the end of desciptors"
        threshold = 1
        last_descriptor = linear_chain_descriptors[-1]

        pubkey_providers = last_descriptor.pubkeys
        if isinstance(last_descriptor, MultisigDescriptor):
            # last descriptor is a multisig
            threshold = last_descriptor.thresh

        return DescriptorInfo(
            address_type=address_type,
            spk_providers=[
                SimplePubKeyProvider.from_hwi(pubkey_provider) for pubkey_provider in pubkey_providers
            ],
            threshold=threshold,
        )
