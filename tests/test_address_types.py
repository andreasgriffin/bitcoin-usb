import pytest

from bitcoin_usb.address_types import AddressTypes, SimplePubKeyProvider, bdk

# test seeds
# seed1: spider manual inform reject arch raccoon betray moon document across main build
# seed2: similar seek stock parent depart rug adjust acoustic oppose sell roast hockey
# seed3: debris yellow child maze hen lamp law venue pluck ketchup melody sick


network = bdk.Network.REGTEST


def test_address_types():
    # https://github.com/bitcoin/bips/blob/master/bip-0044.mediawiki
    assert AddressTypes.p2pkh.key_origin(bdk.Network.REGTEST) == "m/44h/1h/0h"
    assert AddressTypes.p2pkh.key_origin(bdk.Network.BITCOIN) == "m/44h/0h/0h"

    # https://github.com/bitcoin/bips/blob/master/bip-0049.mediawiki
    assert AddressTypes.p2sh_p2wpkh.key_origin(bdk.Network.REGTEST) == "m/49h/1h/0h"
    assert AddressTypes.p2sh_p2wpkh.key_origin(bdk.Network.BITCOIN) == "m/49h/0h/0h"

    # https://github.com/bitcoin/bips/blob/master/bip-0084.mediawiki
    assert AddressTypes.p2wpkh.key_origin(bdk.Network.REGTEST) == "m/84h/1h/0h"
    assert AddressTypes.p2wpkh.key_origin(bdk.Network.BITCOIN) == "m/84h/0h/0h"

    # https://github.com/bitcoin/bips/blob/master/bip-0386.mediawiki   For the purpose-path level it uses 86'. The rest of the levels are used as defined in BIPs 44, 49, and 84.
    assert AddressTypes.p2tr.key_origin(bdk.Network.REGTEST) == "m/86h/1h/0h"
    assert AddressTypes.p2tr.key_origin(bdk.Network.BITCOIN) == "m/86h/0h/0h"

    # https://github.com/bitcoin/bips/blob/master/bip-0048.mediawiki
    assert AddressTypes.p2sh_p2wsh.key_origin(bdk.Network.REGTEST) == "m/48h/1h/0h/1h"
    assert AddressTypes.p2sh_p2wsh.key_origin(bdk.Network.BITCOIN) == "m/48h/0h/0h/1h"

    assert AddressTypes.p2wsh.key_origin(bdk.Network.REGTEST) == "m/48h/1h/0h/2h"
    assert AddressTypes.p2wsh.key_origin(bdk.Network.BITCOIN) == "m/48h/0h/0h/2h"


def test_SimplePubKeyProvider():
    assert SimplePubKeyProvider.format_derivation_path("/ 0'/15 ") == "/0h/15"
    assert SimplePubKeyProvider.format_derivation_path("/ 1/15 ") == "/1/15"
    assert SimplePubKeyProvider.format_derivation_path("/ 1/* ") == "/1/*"
    assert SimplePubKeyProvider.format_derivation_path("/<0; 1>/ *") == "/<0;1>/*"

    assert SimplePubKeyProvider.format_key_origin(" m /   48' / 1' / 1' / 2' ") == "m/48h/1h/1h/2h"
    with pytest.raises(ValueError):
        SimplePubKeyProvider.format_key_origin(" / 48' / 1' / 1' / 2' ")
    with pytest.raises(ValueError):
        SimplePubKeyProvider.format_key_origin("  48' / m/ 1' / 1' / 2' ")
    with pytest.raises(ValueError):
        SimplePubKeyProvider.format_key_origin("m/48hh/1h/1h/2h")
    with pytest.raises(ValueError):
        SimplePubKeyProvider.format_key_origin("m/h/1h/1h/2h")
    with pytest.raises(ValueError):
        SimplePubKeyProvider.format_key_origin("m/h4/1h/1h/2h")
    with pytest.raises(ValueError):
        SimplePubKeyProvider.format_key_origin("m/1h1h4/1h/1h/2h")

    assert SimplePubKeyProvider.format_fingerprint(" 1 " * 8) == "11111111"
    assert SimplePubKeyProvider.format_fingerprint("a" * 8)
    with pytest.raises(ValueError):
        assert SimplePubKeyProvider.format_fingerprint("1" * 7)
    with pytest.raises(ValueError):
        assert SimplePubKeyProvider.format_fingerprint("1" * 2)
    with pytest.raises(ValueError):
        assert SimplePubKeyProvider.format_fingerprint("1" * 9)
    with pytest.raises(ValueError):
        assert SimplePubKeyProvider.format_fingerprint("h" * 8)

    assert SimplePubKeyProvider("xpub1234", "11111111", "m/48h/1h/1h/2h").is_testnet()
    assert not SimplePubKeyProvider("xpub1234", "11111111", "m/48h/0'/1h/2h").is_testnet()

    with pytest.raises(ValueError):
        assert not SimplePubKeyProvider("xpub1234", "11111111", "m/48h/3'/1h/2h").is_testnet()
