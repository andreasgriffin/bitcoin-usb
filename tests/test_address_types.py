import pytest
from hwilib.errors import BadArgumentError
from hwilib.key import HARDENED_FLAG

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

    assert SimplePubKeyProvider(
        "tpubDCPkYWRWsTRZji1938hvWzdDsfQ39aasHz47s3htaKyYSHGdZBoNynBzwQsFS4xn4X4basMr1qL3DcPbjhcVNCzLzGhLoZixu2CAke9Q3hK",
        "11111111",
        "m/48h/1h/1h/2h",
    ).is_testnet()
    assert not SimplePubKeyProvider(
        "tpubDCPkYWRWsTRZji1938hvWzdDsfQ39aasHz47s3htaKyYSHGdZBoNynBzwQsFS4xn4X4basMr1qL3DcPbjhcVNCzLzGhLoZixu2CAke9Q3hK",
        "11111111",
        "m/48h/0'/1h/2h",
    ).is_testnet()

    with pytest.raises(ValueError):
        assert not SimplePubKeyProvider(
            "tpubDCPkYWRWsTRZji1938hvWzdDsfQ39aasHz47s3htaKyYSHGdZBoNynBzwQsFS4xn4X4basMr1qL3DcPbjhcVNCzLzGhLoZixu2CAke9Q3hK",
            "11111111",
            "m/48h/3'/1h/2h",
        ).is_testnet()


# === Tests for format_key_origin ===


def test_format_key_origin_special_case():
    # When the input is just "m", the special case should return "m" immediately.
    result = SimplePubKeyProvider.format_key_origin("m")
    assert result == "m"


def test_format_key_origin_valid1():
    valid_input = "m/44h/0h/1h"
    result = SimplePubKeyProvider.format_key_origin(valid_input)
    # For a valid key origin the input is returned unchanged.
    assert result == valid_input


def test_format_key_origin_valid_with_spaces():
    valid_input = "  m/44h/0h/1h  "
    result = SimplePubKeyProvider.format_key_origin(valid_input)
    assert result == "m/44h/0h/1h"


def test_format_key_origin_no_m_prefix():
    with pytest.raises(ValueError):
        SimplePubKeyProvider.format_key_origin("n/44h/0h/1h")


def test_format_key_origin_double_slash():
    with pytest.raises(ValueError):
        SimplePubKeyProvider.format_key_origin("m//44h/0h/1h")


def test_format_key_origin_contains_slash_h():
    # The string "m/h44/0h/1h" contains the substring "/h" (immediately after the slash) which is forbidden.
    with pytest.raises(ValueError):
        SimplePubKeyProvider.format_key_origin("m/h44/0h/1h")


def test_format_key_origin_contains_hh():
    with pytest.raises(ValueError):
        SimplePubKeyProvider.format_key_origin("m/44hh/0h/1h")


def test_format_key_origin_trailing_slash():
    with pytest.raises(ValueError):
        SimplePubKeyProvider.format_key_origin("m/44h/0h/1h/")


def test_format_key_origin_group_two_h():
    # Any index group that contains more than one "h" (for example "4hh4") should trigger an exception.
    with pytest.raises(ValueError):
        SimplePubKeyProvider.format_key_origin("m/4hh4/0h/1h")


def test_format_key_origin_valid():
    # A valid key origin should be normalized.
    ko = "m/84h/1h/0h"
    result = SimplePubKeyProvider.format_key_origin(ko)
    assert result == "m/84h/1h/0h"


def test_format_key_origin_special_m():
    # The special case "m" should be returned as is.
    result = SimplePubKeyProvider.format_key_origin("m")
    assert result == "m"


def test_format_key_origin_invalid():
    # A key origin not starting with "m" will cause parse_path to raise an error.
    with pytest.raises(ValueError):
        SimplePubKeyProvider.format_key_origin("invalid/84h/1h/0h")


# === Tests for robust_parse_path ===


def test_robust_parse_path_valid1():
    key_origin = "m/44h/0h/1h"
    indexes = SimplePubKeyProvider.robust_parse_path(key_origin)
    expected = [44 | HARDENED_FLAG, 0 | HARDENED_FLAG, 1 | HARDENED_FLAG]
    assert indexes == expected


def test_robust_parse_path_valid():
    path = "m/84h/1h/0h"
    indexes = SimplePubKeyProvider.robust_parse_path(path)
    expected = [84 | HARDENED_FLAG, 1 | HARDENED_FLAG, 0 | HARDENED_FLAG]
    assert indexes == expected


def test_robust_parse_path_invalid():
    # Passing an invalid path should return None.
    indexes = SimplePubKeyProvider.robust_parse_path("not a valid path")
    assert indexes is None


# === Tests for key_origin_indexes_to_str ===


def test_key_origin_indexes_to_str1():
    indexes = [44 | HARDENED_FLAG, 0 | HARDENED_FLAG, 1 | HARDENED_FLAG]
    result = SimplePubKeyProvider.key_origin_indexes_to_str(indexes)
    expected = "m/44h/0h/1h"
    assert result == expected


def test_key_origin_indexes_to_str_empty():
    indexes = []  # type: ignore
    result = SimplePubKeyProvider.key_origin_indexes_to_str(indexes)
    expected = "m"
    assert result == expected


def test_key_origin_indexes_to_str():
    indexes = [84 | HARDENED_FLAG, 1 | HARDENED_FLAG, 0 | HARDENED_FLAG]
    result = SimplePubKeyProvider.key_origin_indexes_to_str(indexes)
    assert result == "m/84h/1h/0h"


# --- Tests for fingerprint formatting ---


def test_format_fingerprint_valid():
    # Valid fingerprint should be converted to uppercase.
    fp = "abcdef01"
    result = SimplePubKeyProvider.format_fingerprint(fp)
    assert result == "ABCDEF01"


def test_format_fingerprint_invalid():
    # Fingerprint with incorrect length or non-hex should raise ValueError.
    with pytest.raises(ValueError):
        SimplePubKeyProvider.format_fingerprint("abc")  # too short
    with pytest.raises(ValueError):
        SimplePubKeyProvider.format_fingerprint("GGGGGGGG")  # not valid hex


# --- Tests for derivation path formatting ---


def test_format_derivation_path_valid():
    # Leading spaces are removed and a trailing "'" is replaced by "h"
    dp = "  /0/*'  "
    result = SimplePubKeyProvider.format_derivation_path(dp)
    assert result == "/0/*h"


def test_format_derivation_path_invalid():
    # Derivation path must start with a "/"
    with pytest.raises(ValueError):
        SimplePubKeyProvider.format_derivation_path("0/*")


# === Tests for get_network_index ===


def test_get_network_index_valid1():
    key_origin = "m/44h/0h/1h"
    # For "m/44h/0h/1h":
    #   - parse_path returns [44|H, 0|H, 1|H]
    #   - The network index is the second element (0|H), so the method should return 0.
    result = SimplePubKeyProvider.get_network_index(key_origin)
    assert result == 0


def test_get_network_index_too_few_levels():
    # A key origin with too few levels (only one index after "m/") should return None.
    key_origin = "m/44h"
    result = SimplePubKeyProvider.get_network_index(key_origin)
    assert result is None


def test_get_network_index_not_hardened1():
    # If the second index is not hardened, the method should return None.
    key_origin = "m/44h/0/1h"  # "0" is not hardened.
    result = SimplePubKeyProvider.get_network_index(key_origin)
    assert result is None


def test_get_network_index_valid():
    # For a valid key origin, the network index (second element) should be extracted.
    key_origin = "m/84h/1h/0h"
    index = SimplePubKeyProvider.get_network_index(key_origin)
    # 1h means 1 | HARDENED_FLAG, and after stripping the hardened flag, the result should be 1.
    assert index == 1


def test_get_network_index_not_hardened():
    # If the network index is not hardened, get_network_index returns None.
    key_origin = "m/84h/1/0h"  # "1" is not hardened.
    index = SimplePubKeyProvider.get_network_index(key_origin)
    assert index is None


# === Tests for get_account_index ===


def test_get_account_index_valid1():
    key_origin = "m/44h/0h/1h"
    # The account index (third element) is 1|H, so the method should return 1.
    result = SimplePubKeyProvider.get_account_index(key_origin)
    assert result == 1


def test_get_account_index_too_few_levels():
    # A key origin with only two indexes (after "m/") should not have an account index.
    key_origin = "m/44h/0h"
    assert SimplePubKeyProvider.get_account_index(key_origin) is None


def test_get_account_index_not_hardened1():
    # If the account index is not hardened, the method should return None.
    key_origin = "m/44h/0h/1"  # "1" is not hardened.
    result = SimplePubKeyProvider.get_account_index(key_origin)
    assert result is None


def test_get_account_index_valid():
    # For a valid key origin, the account index (third element) should be extracted.
    key_origin = "m/84h/1h/0h"
    index = SimplePubKeyProvider.get_account_index(key_origin)
    assert index == 0


def test_get_account_index_not_hardened():
    # If the account index is not hardened, get_account_index returns None.
    key_origin = "m/84h/1h/0"  # "0" is not hardened.
    index = SimplePubKeyProvider.get_account_index(key_origin)
    assert index is None


# === Tests for key_origin_differs_only_in_account ===


def test_key_origin_differs_only_in_account_true():
    key_origin1 = "m//44h/0h/1h"
    key_origin2 = "m/44h/0h/2h"  # the account index of key_origin2 (2) is not used in the comparison
    result = SimplePubKeyProvider.key_origin_identical_disregarding_account(key_origin1, key_origin2)
    assert not result

    key_origin1 = "m/44h/0h/1h"
    key_origin2 = "m/44'/0h/2h"  # the account index of key_origin2 (2) is not used in the comparison
    result = SimplePubKeyProvider.key_origin_identical_disregarding_account(key_origin1, key_origin2)
    assert result

    # When key_origin1 is given in standard (non-normalized) form, the re-stringification
    # (which produces an extra slash) won’t match and the method returns False.
    key_origin1 = "m/44h/0h/1h"
    key_origin2 = "m/44'/0h/1h"
    result = SimplePubKeyProvider.key_origin_identical_disregarding_account(key_origin1, key_origin2)
    assert result


def test_key_origin_differs_only_in_account_false_invalid():
    # If key_origin1 cannot be parsed properly, the method should return False.
    key_origin1 = "invalid"
    key_origin2 = "m/44h/0h/1h"
    result = SimplePubKeyProvider.key_origin_identical_disregarding_account(key_origin1, key_origin2)
    assert result is False


def test_key_origin_identical_up_to_account_identical():
    # Compare the same key origin.
    key_origin1 = "m/84h/1h/0h"
    key_origin2 = "m/84h/1h/0h"
    assert SimplePubKeyProvider.key_origin_identical_disregarding_account(key_origin1, key_origin2)

    # hardening character
    key_origin1 = "m/84h/1h/0h"
    key_origin2 = "m/84'/1'/21000000'"
    assert SimplePubKeyProvider.key_origin_identical_disregarding_account(key_origin1, key_origin2)


def test_key_origin_identical_up_to_account_not_identical():
    key_origin1 = "m/48h/1h/0h/2h"  # multisig default
    key_origin2 = "m/48h/1h/0h/4h"  # non standart
    assert not SimplePubKeyProvider.key_origin_identical_disregarding_account(key_origin1, key_origin2)

    key_origin1 = "m/84h/1h/0h"
    key_origin2 = "m/84h/2h/0h"
    assert not SimplePubKeyProvider.key_origin_identical_disregarding_account(key_origin1, key_origin2)

    key_origin1 = "m/14h/1h/0h"
    key_origin2 = "m/84h/1h/0h"
    assert not SimplePubKeyProvider.key_origin_identical_disregarding_account(key_origin1, key_origin2)

    key_origin1 = "invalid"
    key_origin2 = "m/84h/1h/0h"
    assert not SimplePubKeyProvider.key_origin_identical_disregarding_account(key_origin1, key_origin2)


def test_key_origin_identical_up_to_account_nonstandard():
    # Even when key_origin2 has a different account index,
    # the method ends up comparing key_origin1 to a version of itself.
    key_origin1 = "m/84h/1h/0h"
    key_origin2 = "m/84h/1h/1h"
    # This test shows the non-standard behavior.
    result = SimplePubKeyProvider.key_origin_identical_disregarding_account(key_origin1, key_origin2)
    # The method will return True as long as key_origin1 is well-formed.
    assert result is True


# --- Tests for xpub ---


def test_valid_xpub():

    valid_xpub = "   tpubDCPkYWRWsTRZji1938hvWzdDsfQ39aasHz47s3htaKyYSHGdZBoNynBzwQsFS4xn4X4basMr1qL3DcPbjhcVNCzLzGhLoZixu2CAke9Q3hK   "
    provider = SimplePubKeyProvider(valid_xpub, "abcdef01", "m/84h/1h/0h", "/0/*")
    # Expect that the xpub is stripped and returned in canonical form.
    assert (
        provider.xpub
        == "tpubDCPkYWRWsTRZji1938hvWzdDsfQ39aasHz47s3htaKyYSHGdZBoNynBzwQsFS4xn4X4basMr1qL3DcPbjhcVNCzLzGhLoZixu2CAke9Q3hK"
    )

    valid_xpub = "   xpub661MyMwAqRbcFtXgS5sYJABqqG9YLmC4Q1Rdap9gSE8NqtwybGhePY2gZ29ESFjqJoCu1Rupje8YtGqsefD265TMg7usUDFdp6W1EGMcet8   "
    provider = SimplePubKeyProvider(valid_xpub, "abcdef01", "m/84h/1h/0h", "/0/*")
    # Expect that the xpub is stripped and returned in canonical form.
    assert (
        provider.xpub
        == "xpub661MyMwAqRbcFtXgS5sYJABqqG9YLmC4Q1Rdap9gSE8NqtwybGhePY2gZ29ESFjqJoCu1Rupje8YtGqsefD265TMg7usUDFdp6W1EGMcet8"
    )


def test_invalid_xpub():
    """
    Test that a valid xpub (even with extra spaces) is accepted,
    validated, and its canonical form is stored.
    """

    invalid_xpub = "   xpub661MyMwAqRbcFtValidData   "
    with pytest.raises(BadArgumentError):
        SimplePubKeyProvider(invalid_xpub, "abcdef01", "m/84h/1h/0h", "/0/*")

    invalid_xpub = "  invalid_xpub_data  "
    with pytest.raises(BadArgumentError):
        SimplePubKeyProvider(invalid_xpub, "abcdef01", "m/84h/1h/0h", "/0/*")

    # just changing t of a tpub to x  is not valid
    invalid_xpub = "   xpubDCPkYWRWsTRZji1938hvWzdDsfQ39aasHz47s3htaKyYSHGdZBoNynBzwQsFS4xn4X4basMr1qL3DcPbjhcVNCzLzGhLoZixu2CAke9Q3hK   "
    with pytest.raises(ValueError):
        SimplePubKeyProvider(invalid_xpub, "abcdef01", "m/84h/1h/0h", "/0/*")
