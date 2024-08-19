import logging
from typing import Optional, Tuple

import bdkpython as bdk
from bitcointx import select_chain_params
from bitcointx.wallet import CCoinExtKey
from mnemonic import Mnemonic

logger = logging.getLogger(__name__)

from .address_types import SimplePubKeyProvider


def get_network_index(key_origin: str) -> Optional[int]:
    splitted = key_origin.split("/")
    if len(splitted) < 3:
        logger.warning(f"{key_origin} has too few levels for a network_index")
        return None

    network_str = splitted[2]
    if not network_str.endswith("h"):
        logger.warning(f"The network index ({network_str}) must be hardened")
        return None

    network_index = int(network_str.replace("h", ""))
    return network_index


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

    if key_origin == "m":
        derived_key = master_key
    else:
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
