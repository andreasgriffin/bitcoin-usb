import logging
from typing import Tuple

import bdkpython as bdk
from mnemonic import Mnemonic

from .address_types import SimplePubKeyProvider

logger = logging.getLogger(__name__)


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

    def strip_derivation_path(s: str) -> str:
        return s[:-2] if s.endswith("/*") else s

    bdk_mnemonic = bdk.Mnemonic.from_string(mnemonic)
    root_secret_key = bdk.DescriptorSecretKey(network, bdk_mnemonic, "")
    fingerprint = root_secret_key.as_public().master_fingerprint()
    derived_secret = root_secret_key.derive(bdk.DerivationPath(key_origin))

    pub_str = strip_derivation_path(str(derived_secret.as_public()))
    assert "]" in pub_str

    xpub = pub_str.split("]")[1]  # only take xpub, not key_origin

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
