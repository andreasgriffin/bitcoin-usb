import logging
from typing import Tuple

import bdkpython as bdk
from bitcointx import select_chain_params
from bitcointx.wallet import CCoinExtKey
from mnemonic import Mnemonic

logger = logging.getLogger(__name__)

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
        raise ValueError(f"Unknown network/coin type {network_str} in {key_origin}")


def get_mnemonic_seed(mnemonic: str):
    mnemo = Mnemonic("english")
    if not mnemo.check(mnemonic):
        raise ValueError("Invalid mnemonic phrase.")
    return mnemo.to_seed(mnemonic)


def derive(mnemonic: str, key_origin: str, network: bdk.Network) -> Tuple[str, str]:
    """returns:
            xpub  (at key_origin)
            fingerprint  (at root)

    Args:
        mnemonic (str): _description_
        key_origin (str): _description_
        network (bdk.Network): _description_

    Raises:
        ValueError: _description_

    Returns:
        Tuple[str, str]: xpub, fingerprint  (where fingerprint is the master fingerprint)
    """
    if not key_origin_fits_network(key_origin, network):
        raise ValueError(f"{key_origin} does not fit the selected network {network}")

    # Select network parameters
    network_params = {
        bdk.Network.BITCOIN: "bitcoin",
        bdk.Network.TESTNET: "bitcoin/testnet",
        bdk.Network.REGTEST: "bitcoin/regtest",
        bdk.Network.SIGNET: "bitcoin/signet",
    }
    select_chain_params(network_params.get(network, "bitcoin"))

    seed_bytes = get_mnemonic_seed(mnemonic)

    # Create a master extended key from the seed
    master_key = CCoinExtKey.from_seed(seed_bytes)

    # Derive the xpub at the specified origin
    derived_key = master_key.derive_path(key_origin)

    # Extract xpub

    xpub = str(derived_key.neuter())

    # Get the fingerprint
    fingerprint = master_key.fingerprint.hex()

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
