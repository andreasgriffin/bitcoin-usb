import base64

import bdkpython as bdk
import pytest
from btclib.b32 import p2wpkh
from btclib.b58 import p2pkh, p2wpkh_p2sh
from btclib.bms import verify
from btclib.key import PrvKeyData

from bitcoin_usb.software_signer import SoftwareSigner

seed = "spider manual inform reject arch raccoon betray moon document across main build"
descriptor = "wpkh([7c85f2b5/84'/1'/0']tpubDCPkYWRWsTRZji1938hvWzdDsfQ39aasHz47s3htaKyYSHGdZBoNynBzwQsFS4xn4X4basMr1qL3DcPbjhcVNCzLzGhLoZixu2CAke9Q3hK/0/*)"
change_descriptor = "wpkh([7c85f2b5/84'/1'/0']tpubDCPkYWRWsTRZji1938hvWzdDsfQ39aasHz47s3htaKyYSHGdZBoNynBzwQsFS4xn4X4basMr1qL3DcPbjhcVNCzLzGhLoZixu2CAke9Q3hK/1/*)"
network = bdk.Network.REGTEST
path = "m/84h/1h/0h/0/0"
multisig_path = "m/48h/1h/0h/2h/0/4"


def _signer() -> SoftwareSigner:
    return SoftwareSigner(
        mnemonic=seed,
        network=network,
        receive_descriptor=descriptor,
        change_descriptor=change_descriptor,
    )


def _private_key_for(bip32_path: str) -> PrvKeyData:
    root = bdk.DescriptorSecretKey(bdk.NetworkKind.TEST, bdk.Mnemonic.from_string(seed), "")
    secret = bytes(root.derive(bdk.DerivationPath(bip32_path)).secret_bytes())
    return PrvKeyData(int.from_bytes(secret, "big"), "regtest", compressed=True)


def _decode(signature: str) -> bytes:
    raw = base64.b64decode(signature, validate=True)
    assert len(raw) == 65
    return raw


def test_sign_message_header_is_native_segwit_bip137() -> None:
    raw = _decode(_signer().sign_message("hello world", path))

    # BIP137: P2WPKH uses header range 39-42
    assert 39 <= raw[0] <= 42


def test_sign_message_verifies_for_native_segwit_address() -> None:
    signature = _signer().sign_message("hello world", path)

    assert verify(b"hello world".hex(), p2wpkh(_private_key_for(path).pub), signature)


def test_sign_message_other_message_does_not_verify() -> None:
    signature = _signer().sign_message("hello world", path)

    assert not verify(b"other message".hex(), p2wpkh(_private_key_for(path).pub), signature)


def test_sign_message_bip48_succeeds() -> None:
    signature = _signer().sign_message("hello world", multisig_path)

    raw = _decode(signature)
    assert 31 <= raw[0] <= 34


def test_sign_message_bip48_verifies_against_derived_p2pkh_address() -> None:
    signature = _signer().sign_message("hello world", multisig_path)
    address = p2pkh(_private_key_for(multisig_path).pub)

    assert verify(b"hello world".hex(), address, signature)
    assert not verify(b"other message".hex(), address, signature)


def test_sign_message_p2pkh_path_uses_legacy_header_range() -> None:
    signature = _signer().sign_message("hello world", "m/44h/1h/0h/0/0")
    raw = _decode(signature)

    assert 31 <= raw[0] <= 34
    assert verify(b"hello world".hex(), p2pkh(_private_key_for("m/44h/1h/0h/0/0").pub), signature)


def test_sign_message_p2sh_p2wpkh_path_uses_bip137_header_range() -> None:
    signature = _signer().sign_message("hello world", "m/49h/1h/0h/0/0")
    raw = _decode(signature)

    assert 35 <= raw[0] <= 38
    assert verify(b"hello world".hex(), p2wpkh_p2sh(_private_key_for("m/49h/1h/0h/0/0").pub), signature)


@pytest.mark.parametrize("invalid_path", ["m/84h/x/0", "not-a-path", "m/84h/1h/0h/0/-1"])
def test_sign_message_invalid_path_raises(invalid_path: str) -> None:
    with pytest.raises(bdk.bdk.Bip32Error):
        _signer().sign_message("hello world", invalid_path)
