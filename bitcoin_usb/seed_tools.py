import logging
from typing import Tuple

import bdkpython as bdk

logger = logging.getLogger(__name__)

from bip_utils import (
    Bip32FingerPrint,
    Bip32KeyData,
    Bip32KeyIndex,
    Bip32PrivateKeySerializer,
    Bip32Slip10Secp256k1,
    Bip39Languages,
    Bip39MnemonicDecoder,
    Bip39SeedGenerator,
)
from bip_utils.bip.bip32 import Bip32Const, Bip32PublicKeySerializer

from .address_types import SimplePubKeyProvider


def key_origin_fits_network(key_origin: str, network: bdk.Network):
    network_str = key_origin.split("/")[2]
    assert network_str.endswith("h")
    network_index = int(network_str.replace("h", ""))

    if network_index == 0:
        return network == bdk.Network.BITCOIN
    elif network_index == 1:
        return network != bdk.Network.BITCOIN
    else:
        # https://learnmeabitcoin.com/technical/derivation-paths
        raise ValueError(f"Unknown network/coin type {network_str} in {key_origin}")


def get_bip32_ext_private_key(mnemonic: str, network: bdk.Network):
    # Attempt to decode the mnemonic (this will also validate it)
    try:
        Bip39MnemonicDecoder(Bip39Languages.ENGLISH).Decode(mnemonic)
    except ValueError as e:
        raise ValueError("Invalid mnemonic phrase.") from e

    # Generate seed from mnemonic
    seed_bytes = Bip39SeedGenerator(mnemonic).Generate()

    # Create a Bip32 object using SLIP-0010 for the secp256k1 curve (used by Bitcoin)
    bip32_master_key = Bip32Slip10Secp256k1.FromSeed(seed_bytes)

    net_ver = (
        Bip32Const.MAIN_NET_KEY_NET_VERSIONS
        if network == bdk.Network.BITCOIN
        else Bip32Const.TEST_NET_KEY_NET_VERSIONS
    )

    # Get the private key object (IPrivateKey instance)
    priv_key = bip32_master_key.PrivateKey()

    # Create Bip32KeyData for the master key
    key_data = Bip32KeyData(
        depth=0,
        parent_fprint=Bip32FingerPrint(),
        index=Bip32KeyIndex(0),
        chain_code=bip32_master_key.ChainCode(),
    )

    # Serialize the private key with the specified network version
    return Bip32PrivateKeySerializer.Serialize(priv_key, key_data, net_ver)


def derive(mnemonic: str, key_origin: str, network: bdk.Network) -> Tuple[str, str]:
    """
    Derive the extended public key (xpub/tpub) from a given mnemonic, derivation path, and network version.

    :param mnemonic: A valid BIP39 mnemonic phrase.
    :param derivation_path: The derivation path in a format like "m/44'/0'/0'".
    :param network:
    :return: The extended public key in xpub/tpub format.
    """
    if not key_origin_fits_network(key_origin, network):
        raise ValueError(f"{key_origin} does not fit to the selected network {network}")

    # Attempt to decode the mnemonic (this will also validate it)
    try:
        Bip39MnemonicDecoder(Bip39Languages.ENGLISH).Decode(mnemonic)
    except ValueError as e:
        raise ValueError("Invalid mnemonic phrase.") from e

    # Generate seed from mnemonic
    seed_bytes = Bip39SeedGenerator(mnemonic).Generate()

    # Create a Bip32 object using SLIP-0010 for the secp256k1 curve (used by Bitcoin)
    bip32_obj = Bip32Slip10Secp256k1.FromSeed(seed_bytes)

    # Derive the path
    bip32_base = bip32_obj.DerivePath(key_origin)

    net_ver = (
        Bip32Const.MAIN_NET_KEY_NET_VERSIONS
        if network == bdk.Network.BITCOIN
        else Bip32Const.TEST_NET_KEY_NET_VERSIONS
    )

    # Serialize the public key with the specified network version
    xpub = Bip32PublicKeySerializer.Serialize(
        bip32_base.PublicKey().m_pub_key, bip32_base.PublicKey().m_key_data, net_ver
    )
    fingerprint = bip32_obj.FingerPrint().ToHex()
    return xpub, fingerprint


def derive_spk_provider(
    mnemonic: str, key_origin: str, network: bdk.Network, derivation_path: str = "/0/*"
) -> SimplePubKeyProvider:
    xpub, fingerprint = derive(mnemonic, key_origin, network)
    return SimplePubKeyProvider(
        xpub=xpub,
        fingerprint=fingerprint,
        key_origin=key_origin,
        derivation_path=derivation_path,
    )
