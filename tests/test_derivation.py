import bdkpython as bdk

from bitcoin_usb.address_types import (
    AddressTypes,
    DescriptorInfo,
    SimplePubKeyProvider,
    bdk,
    get_all_address_types,
    logging,
)
from bitcoin_usb.seed_tools import derive_spk_provider

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

            assert address_type.bdk_descriptor_secret
            descriptor = address_type.bdk_descriptor_secret(
                bdk.DescriptorSecretKey(network, bdk.Mnemonic.from_string(test_seed), ""),
                bdk.KeychainKind.EXTERNAL,
                network,
            )

            spk_provider = derive_spk_provider(test_seed, address_type.key_origin(network), network)

            desc_info = DescriptorInfo(address_type, [spk_provider])
            assert str(descriptor) == desc_info.get_hwi_descriptor(network).to_string(hardened_char="'")
            assert str(descriptor) == desc_info.get_descriptor_str(network, hardened_char="'")


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
    assert spk_provider.fingerprint == "7c85f2b5".upper()


def test_unusual_derivations():
    #######
    key_origin = "m"
    spk_provider = derive_spk_provider(
        "spider manual inform reject arch raccoon betray moon document across main build",
        key_origin,
        network,
    )
    print(spk_provider)
    assert spk_provider.key_origin == key_origin
    assert (
        spk_provider.xpub
        == "tpubD6NzVbkrYhZ4YjD4x8pv3PDE9bzSdF6FLsCroncohJbjpx4X9KykvHvZt2E2ybcrAuiNXWkVMt8TuJxYV7YMcgkfytvjMoCssXpL6pUp4Sc"
    )
    # compared with sparrow
    assert spk_provider.fingerprint == "7c85f2b5".upper()

    #######
    key_origin = "m/1234567"
    spk_provider = derive_spk_provider(
        "spider manual inform reject arch raccoon betray moon document across main build",
        key_origin,
        network,
    )
    print(spk_provider)
    assert spk_provider.key_origin == key_origin
    assert (
        spk_provider.xpub
        == "tpubD9BDKDcxLHML2kmMeCuMF5QBETNQncf35TnwPvC5qhtLZupbxLEa4mhrpZZzfgmL8cxVTVUhgmUticQNWipZd19zatMmwg7LLgYjmFkqXpM"
    )
    # compared with sparrow
    assert spk_provider.fingerprint == "7c85f2b5".upper()

    #######
    key_origin = "m/1234567/0h/1"
    spk_provider = derive_spk_provider(
        "spider manual inform reject arch raccoon betray moon document across main build",
        key_origin,
        network,
    )
    print(spk_provider)
    assert spk_provider.key_origin == key_origin
    assert (
        spk_provider.xpub
        == "tpubDDXENRdKZmizWdFbbgVf37n9zZ6yykSUdLYfhoPG2ubUgBVaUShGvdU17BPRwNNtLRrt8jVayR96JoW8yg9TdDo9tg7LeCWCqJ9V7NFnQqL"
    )
    # compared with sparrow
    assert spk_provider.fingerprint == "7c85f2b5".upper()


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
    assert spk_provider.fingerprint == "7c85f2b5".upper()


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
    assert spk_provider.fingerprint == "7c85f2b5".upper()


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
    assert spk_provider.fingerprint == "7c85f2b5".upper()


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
    descriptor = DescriptorInfo(AddressTypes.p2wsh, spk_providers, 2).get_descriptor_str(network)
    stripped = descriptor.split("#")[0].replace("'", "h")
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
    descriptor = DescriptorInfo(AddressTypes.p2wsh, spk_providers, 2).get_descriptor_str(network)
    stripped = descriptor.split("#")[0].replace("'", "h")
    # comparision created with sparrow (had to reorder the pubkey_providers)
    assert (
        stripped
        == "wsh(sortedmulti(2,[7c85f2b5/44h/1h/0h]tpubDCwGRkTC8E2QbbUPZvpXQad4zRHqo24YTJpAFDtJh1x6nTBojiKTorqCm2JQdnDEwLruKry8NTont7tG6jqZCFnp5c2evppfedDdRRAJxrX/0/*,[34be20d9/48h/1h/0h/2h]tpubDEGiMrEBpyW7ebPDipDBwgxi4Ct4VqDApRcDEZy6uT8HoE5jUduJiXH7axkuQdcf7ZGamBbng7Ym3MPwLHqkugswt1uCParZBGyGsfEZ7PQ/0/*,[3b8adfc3/48h/1h/0h/2h]tpubDEmjAPbjr9QfDidVmgSGdK6JYXiFy1xw9pVmXXSbZxa8qz2ixtZhaRyLdMS3wwECPao4PRC4dGWXnpwnzGUAaVewbW9VtkYaMg4neeTFLm6/0/*))"
    )

    assert (
        "m/44h/1h/0h does not match the default key origin m/48h/1h/0h/2h for this address type Multi Sig (SegWit/p2wsh)!"
        == caplog.records[-1].message
    )


def test_get_network_index():
    assert SimplePubKeyProvider.get_network_index("m/48h/0h/0h/2h") == 0
    assert SimplePubKeyProvider.get_network_index("m/48h/1h/0h/2h") == 1

    assert SimplePubKeyProvider.get_network_index("m/48h/1/0h/2h") == None

    assert SimplePubKeyProvider.get_network_index("m/4") == None
