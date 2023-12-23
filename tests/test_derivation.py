from numpy import lookfor
from bitcoin_usb.address_types import *
import pytest
from bitcoin_usb.seed_tools import derive_spk_provider, derive
from unittest.mock import patch

# test seeds
# seed1: spider manual inform reject arch raccoon betray moon document across main build
# seed2: similar seek stock parent depart rug adjust acoustic oppose sell roast hockey
# seed3: debris yellow child maze hen lamp law venue pluck ketchup melody sick


network = bdk.Network.REGTEST


def test_compare_single_sig_key_derivation_with_bdk_templates():
    for test_seed in [
        "spider manual inform reject arch raccoon betray moon document across main build",
        "similar seek stock parent depart rug adjust acoustic oppose sell roast hockey",
        "debris yellow child maze hen lamp law venue pluck ketchup melody sick",
    ]:

        for address_type in get_all_address_types():
            if address_type.is_multisig:
                # no gtest possible yet here, because no bdk_template exists
                continue

            descriptor = address_type.bdk_descriptor_secret(
                secret_key=bdk.DescriptorSecretKey(
                    network, bdk.Mnemonic.from_string(test_seed), ""
                ),
                keychain=bdk.KeychainKind.EXTERNAL,
                network=network,
            )

            spk_provider = derive_spk_provider(
                test_seed, address_type.key_origin(network), network
            )

            desc_info = DescriptorInfo(address_type, [spk_provider])
            assert descriptor.as_string() == desc_info.get_hwi_descriptor(
                network
            ).to_string(hardened_char="'")
            assert (
                descriptor.as_string()
                == desc_info.get_bdk_descriptor(network).as_string()
            )


def test_correct_p2sh_p2wsh_derivation():
    spk_provider = derive_spk_provider(
        "spider manual inform reject arch raccoon betray moon document across main build",
        AddressTypes.p2sh_p2wsh.key_origin(network),
        network,
    )
    print(spk_provider)
    assert spk_provider.key_origin == "m/48h/1h/0h/1h"
    assert (
        spk_provider.xpub
        == "tpubDEBYeoKBCaY1fZ3PSpdYjeedEx5oWowEn8Pa8pS19RWQK5bvAJVFa7Qe8N8e6uCxtwJvwtWiGnHawY3GwbHiUtv17RUpL3FYxckC5QmRWip"
    )
    # compared with sparrow
    assert spk_provider.fingerprint == "7c85f2b5"


def test_correct_p2wsh_derivation():
    spk_provider = derive_spk_provider(
        "spider manual inform reject arch raccoon betray moon document across main build",
        AddressTypes.p2wsh.key_origin(network),
        network,
    )
    print(spk_provider)
    assert spk_provider.key_origin == "m/48h/1h/0h/2h"
    assert (
        spk_provider.xpub
        == "tpubDEBYeoKBCaY1h6353GCojAoPdi7GGz4JYhyac8StrxBWKZCb5nQQQJCFndXFmFGgakmPxS3zQkkCxzKGuLGBKhgfL96jrc6L3rn1D5bAhjo"
    )
    # compared with sparrow
    assert spk_provider.fingerprint == "7c85f2b5"


def test_correct_44derivation():
    spk_provider = derive_spk_provider(
        "spider manual inform reject arch raccoon betray moon document across main build",
        AddressTypes.p2pkh.key_origin(network),
        network,
    )
    print(spk_provider)
    assert spk_provider.key_origin == "m/44h/1h/0h"
    assert (
        spk_provider.xpub
        == "tpubDCwGRkTC8E2QbbUPZvpXQad4zRHqo24YTJpAFDtJh1x6nTBojiKTorqCm2JQdnDEwLruKry8NTont7tG6jqZCFnp5c2evppfedDdRRAJxrX"
    )
    assert spk_provider.fingerprint == "7c85f2b5"


def test_correct_84derivation():
    spk_provider = derive_spk_provider(
        "spider manual inform reject arch raccoon betray moon document across main build",
        AddressTypes.p2wpkh.key_origin(network),
        network,
    )
    print(spk_provider)
    assert spk_provider.key_origin == "m/84h/1h/0h"
    assert (
        spk_provider.xpub
        == "tpubDCPkYWRWsTRZji1938hvWzdDsfQ39aasHz47s3htaKyYSHGdZBoNynBzwQsFS4xn4X4basMr1qL3DcPbjhcVNCzLzGhLoZixu2CAke9Q3hK"
    )
    assert spk_provider.fingerprint == "7c85f2b5"


def test_wrong_network():
    with pytest.raises(ValueError) as exc_info:
        xpub, fingerprint = derive(
            "spider manual inform reject arch raccoon betray moon document across main build",
            "m/48h/0h/0h/2h",
            network,
        )
    assert (
        str(exc_info.value)
        == "m/48h/0h/0h/2h does not fit to the selected network Network.REGTEST"
    )


def test_multisig():
    spk_providers = [
        derive_spk_provider(
            "spider manual inform reject arch raccoon betray moon document across main build",
            AddressTypes.p2wsh.key_origin(network),
            network,
        ),
        derive_spk_provider(
            "similar seek stock parent depart rug adjust acoustic oppose sell roast hockey",
            AddressTypes.p2wsh.key_origin(network),
            network,
        ),
        derive_spk_provider(
            "debris yellow child maze hen lamp law venue pluck ketchup melody sick",
            AddressTypes.p2wsh.key_origin(network),
            network,
        ),
    ]
    descriptor = DescriptorInfo(
        AddressTypes.p2wsh, spk_providers, 2
    ).get_bdk_descriptor(network)
    stripped = descriptor.as_string().split("#")[0].replace("'", "h")
    # comparision created with sparrow (had to reorder the pubkey_providers)
    assert (
        stripped
        == "wsh(sortedmulti(2,[7c85f2b5/48h/1h/0h/2h]tpubDEBYeoKBCaY1h6353GCojAoPdi7GGz4JYhyac8StrxBWKZCb5nQQQJCFndXFmFGgakmPxS3zQkkCxzKGuLGBKhgfL96jrc6L3rn1D5bAhjo/0/*,[34be20d9/48h/1h/0h/2h]tpubDEGiMrEBpyW7ebPDipDBwgxi4Ct4VqDApRcDEZy6uT8HoE5jUduJiXH7axkuQdcf7ZGamBbng7Ym3MPwLHqkugswt1uCParZBGyGsfEZ7PQ/0/*,[3b8adfc3/48h/1h/0h/2h]tpubDEmjAPbjr9QfDidVmgSGdK6JYXiFy1xw9pVmXXSbZxa8qz2ixtZhaRyLdMS3wwECPao4PRC4dGWXnpwnzGUAaVewbW9VtkYaMg4neeTFLm6/0/*))"
    )


def test_multisig_unusual_key_origin(caplog):
    caplog.set_level(logging.WARNING)
    spk_providers = [
        derive_spk_provider(
            "spider manual inform reject arch raccoon betray moon document across main build",
            AddressTypes.p2pkh.key_origin(network),
            network,
        ),
        derive_spk_provider(
            "similar seek stock parent depart rug adjust acoustic oppose sell roast hockey",
            AddressTypes.p2wsh.key_origin(network),
            network,
        ),
        derive_spk_provider(
            "debris yellow child maze hen lamp law venue pluck ketchup melody sick",
            AddressTypes.p2wsh.key_origin(network),
            network,
        ),
    ]
    descriptor = DescriptorInfo(
        AddressTypes.p2wsh, spk_providers, 2
    ).get_bdk_descriptor(network)
    stripped = descriptor.as_string().split("#")[0].replace("'", "h")
    # comparision created with sparrow (had to reorder the pubkey_providers)
    assert (
        stripped
        == "wsh(sortedmulti(2,[7c85f2b5/44h/1h/0h]tpubDCwGRkTC8E2QbbUPZvpXQad4zRHqo24YTJpAFDtJh1x6nTBojiKTorqCm2JQdnDEwLruKry8NTont7tG6jqZCFnp5c2evppfedDdRRAJxrX/0/*,[34be20d9/48h/1h/0h/2h]tpubDEGiMrEBpyW7ebPDipDBwgxi4Ct4VqDApRcDEZy6uT8HoE5jUduJiXH7axkuQdcf7ZGamBbng7Ym3MPwLHqkugswt1uCParZBGyGsfEZ7PQ/0/*,[3b8adfc3/48h/1h/0h/2h]tpubDEmjAPbjr9QfDidVmgSGdK6JYXiFy1xw9pVmXXSbZxa8qz2ixtZhaRyLdMS3wwECPao4PRC4dGWXnpwnzGUAaVewbW9VtkYaMg4neeTFLm6/0/*))"
    )

    assert (
        "m/44h/1h/0h is not a common multisig key_origin!" == caplog.records[-1].message
    )
