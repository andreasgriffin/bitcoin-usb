import base64

import bdkpython as bdk
from btclib.bms import verify

from btclib.key import PrvKeyData
from btclib.b32 import p2wpkh

from bitcoin_usb.software_signer import SoftwareSigner

seed = "spider manual inform reject arch raccoon betray moon document across main build"
descriptor = "wpkh([7c85f2b5/84'/1'/0']tpubDCPkYWRWsTRZji1938hvWzdDsfQ39aasHz47s3htaKyYSHGdZBoNynBzwQsFS4xn4X4basMr1qL3DcPbjhcVNCzLzGhLoZixu2CAke9Q3hK/0/*)"
change_descriptor = "wpkh([7c85f2b5/84'/1'/0']tpubDCPkYWRWsTRZji1938hvWzdDsfQ39aasHz47s3htaKyYSHGdZBoNynBzwQsFS4xn4X4basMr1qL3DcPbjhcVNCzLzGhLoZixu2CAke9Q3hK/1/*)"
network = bdk.Network.REGTEST
path = "m/84h/1h/0h/0/0"


def _signer() -> SoftwareSigner:
    return SoftwareSigner(
        mnemonic=seed,
        network=network,
        receive_descriptor=descriptor,
        change_descriptor=change_descriptor,
    )


def _expected_address() -> str:
    root = bdk.DescriptorSecretKey(bdk.NetworkKind.TEST, bdk.Mnemonic.from_string(seed), "")
    secret = bytes(root.derive(bdk.DerivationPath(path)).secret_bytes())
    return p2wpkh(PrvKeyData(int.from_bytes(secret, "big"), "regtest", compressed=True).pub)


def _decode(signature: str) -> bytes:
    raw = base64.b64decode(signature)
    assert len(raw) == 65
    return raw


def test_sign_message_header_is_native_segwit_bip137() -> None:
    raw = _decode(_signer().sign_message("hello world", path))

    # BIP137: P2WPKH uses header range 39-42
    assert 39 <= raw[0] <= 42


def test_sign_message_verifies_for_native_segwit_address() -> None:
    signature = _signer().sign_message("hello world", path)

    assert verify(b"hello world".hex(), _expected_address(), signature)


def test_sign_message_other_message_does_not_verify() -> None:
    signature = _signer().sign_message("hello world", path)

    assert not verify(b"other message".hex(), _expected_address(), signature)


def test_sign_message_p2pkh_path_uses_legacy_header_range() -> None:
    raw = _decode(_signer().sign_message("hello world", "m/44h/1h/0h/0/0"))

    assert 31 <= raw[0] <= 34
