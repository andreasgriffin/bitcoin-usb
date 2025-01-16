import pytest
from hwilib.descriptor import parse_descriptor

from bitcoin_usb.address_types import DescriptorInfo


def test_xpub_at_root():
    # without /m
    s = "wpkh([45f35351]tpubDEY3tNWvDs8J6xAmwoirxgff61gPN1V6U5numeb6xjvZRB883NPPpRYHt2A6fUE3YyzDLezFfuosBdXsdXJhJUcpqYWF9EEBmWqG3rG8sdy/<0;1>/*)"
    descriptor_info = DescriptorInfo.from_str(s)

    assert descriptor_info.address_type.name == "Single Sig (SegWit/p2wpkh)"
    assert len(descriptor_info.spk_providers) == 1
    assert (
        descriptor_info.spk_providers[0].xpub
        == "tpubDEY3tNWvDs8J6xAmwoirxgff61gPN1V6U5numeb6xjvZRB883NPPpRYHt2A6fUE3YyzDLezFfuosBdXsdXJhJUcpqYWF9EEBmWqG3rG8sdy"
    )
    assert descriptor_info.spk_providers[0].fingerprint == "45F35351"
    assert descriptor_info.spk_providers[0].key_origin == "m"
    assert descriptor_info.spk_providers[0].derivation_path == "/<0;1>/*"

    # with /m
    s = "wpkh([45f35351/m]tpubDEY3tNWvDs8J6xAmwoirxgff61gPN1V6U5numeb6xjvZRB883NPPpRYHt2A6fUE3YyzDLezFfuosBdXsdXJhJUcpqYWF9EEBmWqG3rG8sdy/<0;1>/*)"
    # hwi lib can handle this /m
    assert (
        parse_descriptor(s).to_string()
        == "wpkh([45f35351]tpubDEY3tNWvDs8J6xAmwoirxgff61gPN1V6U5numeb6xjvZRB883NPPpRYHt2A6fUE3YyzDLezFfuosBdXsdXJhJUcpqYWF9EEBmWqG3rG8sdy/<0;1>/*)#xampmc0t"
    )

    descriptor_info = DescriptorInfo.from_str(s)

    assert descriptor_info.address_type.name == "Single Sig (SegWit/p2wpkh)"
    assert len(descriptor_info.spk_providers) == 1
    assert (
        descriptor_info.spk_providers[0].xpub
        == "tpubDEY3tNWvDs8J6xAmwoirxgff61gPN1V6U5numeb6xjvZRB883NPPpRYHt2A6fUE3YyzDLezFfuosBdXsdXJhJUcpqYWF9EEBmWqG3rG8sdy"
    )
    assert descriptor_info.spk_providers[0].fingerprint == "45F35351"
    assert descriptor_info.spk_providers[0].key_origin == "m"
    assert descriptor_info.spk_providers[0].derivation_path == "/<0;1>/*"

    # test
    pubkey_provider = descriptor_info.spk_providers[0].to_hwi_pubkey_provider()
    pubkey_provider.deriv_path == "/<0;1>/*"
    pubkey_provider.origin.to_string() == "m"
    pubkey_provider.to_string() == "[45f35351]tpubDEY3tNWvDs8J6xAmwoirxgff61gPN1V6U5numeb6xjvZRB883NPPpRYHt2A6fUE3YyzDLezFfuosBdXsdXJhJUcpqYWF9EEBmWqG3rG8sdy/<0;1>/*"


def test_pkh():
    s = "pkh([5c625f18/44'/1'/0']tpubDCJ4bZsuPx1rL5ogtqqQZRndeBJADVsRTmd9f6XvT3QyR7yW8DipmbM2QnabWYpVWoaUv2ECBzoaFaDu5B5pMhrFMDJMdPrxiZUKtFHA4CK/<0;1>/*)#6dxlp93s"
    info = DescriptorInfo.from_str(s)
    assert info.address_type.short_name == "p2pkh"
    assert len(info.spk_providers) == 1

    assert info.spk_providers[0].__dict__ == {
        "xpub": "tpubDCJ4bZsuPx1rL5ogtqqQZRndeBJADVsRTmd9f6XvT3QyR7yW8DipmbM2QnabWYpVWoaUv2ECBzoaFaDu5B5pMhrFMDJMdPrxiZUKtFHA4CK",
        "fingerprint": "5C625F18",
        "key_origin": "m/44h/1h/0h",
        "derivation_path": "/<0;1>/*",
    }


def test_sh_wpkh():
    s = "sh(wpkh([61d9fb0d/49'/1'/0']tpubDC6tAvcGsNjbkWfhktGHVeEqWg1bfxY3foqmPzHGZApmvrH1PJaDWPNtBH8mnFAPSLsVqisa6s8fWfeLb6cvh12hDwyBxPDgties2gGVxHU/<0;1>/*))#dlgvzh9k"
    info = DescriptorInfo.from_str(s)
    assert info.address_type.short_name == "p2sh-p2wpkh"
    assert len(info.spk_providers) == 1

    assert info.spk_providers[0].__dict__ == {
        "xpub": "tpubDC6tAvcGsNjbkWfhktGHVeEqWg1bfxY3foqmPzHGZApmvrH1PJaDWPNtBH8mnFAPSLsVqisa6s8fWfeLb6cvh12hDwyBxPDgties2gGVxHU",
        "fingerprint": "61D9FB0D",
        "key_origin": "m/49h/1h/0h",
        "derivation_path": "/<0;1>/*",
    }


def test_wpkh():
    s = "wpkh([b0c08f62/84'/1'/0']tpubDCX7cUd5o2ZzNVwxmM6s9XCXsDzWwybZG7QkMAUHfcDkVjeGg9qdT1U8ms1qjFHCHfv6AZ3LyEUtw6r9jYhjnuH3Znqb9RcEfEjbNcVpE6n/<0;1>/*)#m26udjf3"
    info = DescriptorInfo.from_str(s)
    assert info.address_type.short_name == "p2wpkh"
    assert len(info.spk_providers) == 1

    assert info.spk_providers[0].__dict__ == {
        "xpub": "tpubDCX7cUd5o2ZzNVwxmM6s9XCXsDzWwybZG7QkMAUHfcDkVjeGg9qdT1U8ms1qjFHCHfv6AZ3LyEUtw6r9jYhjnuH3Znqb9RcEfEjbNcVpE6n",
        "fingerprint": "B0C08F62",
        "key_origin": "m/84h/1h/0h",
        "derivation_path": "/<0;1>/*",
    }


def test_tr():
    s = "tr([fc70ecd1/86'/1'/0']tpubDDjw7hTGCWodCZGZqW8mLoJ5kmyRtwouKvs589XfZa4rSXBEzz418LjwzBGiz7QeDoSPYZGy2eCGw3RVcwM4mV93TRBsAHuHb7YfqVQXN32/<0;1>/*)#z3x0aash"
    info = DescriptorInfo.from_str(s)
    assert info.address_type.short_name == "p2tr"
    assert len(info.spk_providers) == 1

    assert info.spk_providers[0].__dict__ == {
        "xpub": "tpubDDjw7hTGCWodCZGZqW8mLoJ5kmyRtwouKvs589XfZa4rSXBEzz418LjwzBGiz7QeDoSPYZGy2eCGw3RVcwM4mV93TRBsAHuHb7YfqVQXN32",
        "fingerprint": "FC70ECD1",
        "key_origin": "m/86h/1h/0h",
        "derivation_path": "/<0;1>/*",
    }


def test_nested_multisig():
    s = "sh(wsh(sortedmulti(1,[c4805c47/48'/1'/0'/1']tpubDE5iLfTxVQQuodr5b4VYc6C9Q3PSj6ufktH5mM7Dcc3iDyw79SHx9cB2XvRVAKgiJsyXr5azeNJULES6RyMiGy723bU4PZaM8CDCQvMrUBZ/<0;1>/*,[a13d6031/48'/1'/0'/1']tpubDEvPb61qFHjagvft8hdmAGRF2qf5KaxCjK3fxL3aUXy3rDgySVqLLjgHQSiw1NuGL1uy8QXdj43asyj64PX9P4aPZLNJGJGNNfEd8VD52WX/<0;1>/*)))#4hw84dmr"
    info = DescriptorInfo.from_str(s)
    assert info.address_type.short_name == "p2sh-p2wsh"
    assert len(info.spk_providers) == 2

    assert info.spk_providers[0].__dict__ == {
        "xpub": "tpubDE5iLfTxVQQuodr5b4VYc6C9Q3PSj6ufktH5mM7Dcc3iDyw79SHx9cB2XvRVAKgiJsyXr5azeNJULES6RyMiGy723bU4PZaM8CDCQvMrUBZ",
        "fingerprint": "C4805C47",
        "key_origin": "m/48h/1h/0h/1h",
        "derivation_path": "/<0;1>/*",
    }
    assert info.spk_providers[1].__dict__ == {
        "xpub": "tpubDEvPb61qFHjagvft8hdmAGRF2qf5KaxCjK3fxL3aUXy3rDgySVqLLjgHQSiw1NuGL1uy8QXdj43asyj64PX9P4aPZLNJGJGNNfEd8VD52WX",
        "fingerprint": "A13D6031",
        "key_origin": "m/48h/1h/0h/1h",
        "derivation_path": "/<0;1>/*",
    }


def test_wsh_multisig():
    s = "wsh(sortedmulti(2,[45f35351/48h/1h/0h/2h]tpubDEY3tNWvDs8J6xAmwoirxgff61gPN1V6U5numeb6xjvZRB883NPPpRYHt2A6fUE3YyzDLezFfuosBdXsdXJhJUcpqYWF9EEBmWqG3rG8sdy/<0;1>/*,[829074ff/48h/1h/0h/2h]tpubDDx9arPwEvHGnnkKN1YJXFE4W6JZXyVX9HGjZW75nWe1FCsTYu2k3i7VtCwhGR9zj6UUYnseZUnwL7T6Znru3NmXkcjEQxMqRx7Rxz8rPp4/<0;1>/*,[d5b43540/48h/1h/0h/2h]tpubDFnCcKU3iUF4sPeQC68r2ewDaBB7TvLmQBTs12hnNS8nu6CPjZPmzapp7Woz6bkFuLfSjSpg6gacheKBaWBhDnEbEpKtCnVFdQnfhYGkPQF/<0;1>/*))#54uq36v8"
    info = DescriptorInfo.from_str(s)
    assert info.address_type.short_name == "p2wsh"
    assert len(info.spk_providers) == 3

    assert info.spk_providers[0].__dict__ == {
        "xpub": "tpubDDx9arPwEvHGnnkKN1YJXFE4W6JZXyVX9HGjZW75nWe1FCsTYu2k3i7VtCwhGR9zj6UUYnseZUnwL7T6Znru3NmXkcjEQxMqRx7Rxz8rPp4",
        "fingerprint": "829074FF",
        "key_origin": "m/48h/1h/0h/2h",
        "derivation_path": "/<0;1>/*",
    }
    assert info.spk_providers[1].__dict__ == {
        "xpub": "tpubDEY3tNWvDs8J6xAmwoirxgff61gPN1V6U5numeb6xjvZRB883NPPpRYHt2A6fUE3YyzDLezFfuosBdXsdXJhJUcpqYWF9EEBmWqG3rG8sdy",
        "fingerprint": "45F35351",
        "key_origin": "m/48h/1h/0h/2h",
        "derivation_path": "/<0;1>/*",
    }
    assert info.spk_providers[2].__dict__ == {
        "xpub": "tpubDFnCcKU3iUF4sPeQC68r2ewDaBB7TvLmQBTs12hnNS8nu6CPjZPmzapp7Woz6bkFuLfSjSpg6gacheKBaWBhDnEbEpKtCnVFdQnfhYGkPQF",
        "fingerprint": "D5B43540",
        "key_origin": "m/48h/1h/0h/2h",
        "derivation_path": "/<0;1>/*",
    }


def test_unsupported_sh():
    s = "sh(sortedmulti(2,[45f35351/48h/1h/0h/2h]tpubDEY3tNWvDs8J6xAmwoirxgff61gPN1V6U5numeb6xjvZRB883NPPpRYHt2A6fUE3YyzDLezFfuosBdXsdXJhJUcpqYWF9EEBmWqG3rG8sdy/<0;1>/*,[829074ff/48h/1h/0h/2h]tpubDDx9arPwEvHGnnkKN1YJXFE4W6JZXyVX9HGjZW75nWe1FCsTYu2k3i7VtCwhGR9zj6UUYnseZUnwL7T6Znru3NmXkcjEQxMqRx7Rxz8rPp4/<0;1>/*,[d5b43540/48h/1h/0h/2h]tpubDFnCcKU3iUF4sPeQC68r2ewDaBB7TvLmQBTs12hnNS8nu6CPjZPmzapp7Woz6bkFuLfSjSpg6gacheKBaWBhDnEbEpKtCnVFdQnfhYGkPQF/<0;1>/*))"

    with pytest.raises(ValueError) as exc_info:
        DescriptorInfo.from_str(s)

    # Extract the exception message
    exception_message = str(exc_info.value)

    # Compare the exception message
    assert (
        exception_message
        == "descriptor sh(sortedmulti(2,[45f35351/48h/1h/0h/2h]tpubDEY3tNWvDs8J6xAmwoirxgff61gPN1V6U5numeb6xjvZRB883NPPpRYHt2A6fUE3YyzDLezFfuosBdXsdXJhJUcpqYWF9EEBmWqG3rG8sdy/<0;1>/*,[829074ff/48h/1h/0h/2h]tpubDDx9arPwEvHGnnkKN1YJXFE4W6JZXyVX9HGjZW75nWe1FCsTYu2k3i7VtCwhGR9zj6UUYnseZUnwL7T6Znru3NmXkcjEQxMqRx7Rxz8rPp4/<0;1>/*,[d5b43540/48h/1h/0h/2h]tpubDFnCcKU3iUF4sPeQC68r2ewDaBB7TvLmQBTs12hnNS8nu6CPjZPmzapp7Woz6bkFuLfSjSpg6gacheKBaWBhDnEbEpKtCnVFdQnfhYGkPQF/<0;1>/*)) cannot be matched to a supported template. Supported templates are ['p2pkh', 'p2sh-p2wpkh', 'p2wpkh', 'p2tr', 'p2sh-p2wsh', 'p2wsh']"
    )


def test_unsupported_type2():
    s = "sh(sh(sortedmulti(1,[45f35351/48h/1h/0h/2h]tpubDEY3tNWvDs8J6xAmwoirxgff61gPN1V6U5numeb6xjvZRB883NPPpRYHt2A6fUE3YyzDLezFfuosBdXsdXJhJUcpqYWF9EEBmWqG3rG8sdy/<0;1>/**)))"

    with pytest.raises(ValueError) as exc_info:
        DescriptorInfo.from_str(s)

    # Extract the exception message
    exception_message = str(exc_info.value)

    # Compare the exception message
    assert exception_message == "Can only have sh() at top level"
