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


def test_multisig():
    s = "wsh(sortedmulti(2,[45f35351/48h/1h/0h/2h]tpubDEY3tNWvDs8J6xAmwoirxgff61gPN1V6U5numeb6xjvZRB883NPPpRYHt2A6fUE3YyzDLezFfuosBdXsdXJhJUcpqYWF9EEBmWqG3rG8sdy/<0;1>/*,[829074ff/48h/1h/0h/2h]tpubDDx9arPwEvHGnnkKN1YJXFE4W6JZXyVX9HGjZW75nWe1FCsTYu2k3i7VtCwhGR9zj6UUYnseZUnwL7T6Znru3NmXkcjEQxMqRx7Rxz8rPp4/<0;1>/*,[d5b43540/48h/1h/0h/2h]tpubDFnCcKU3iUF4sPeQC68r2ewDaBB7TvLmQBTs12hnNS8nu6CPjZPmzapp7Woz6bkFuLfSjSpg6gacheKBaWBhDnEbEpKtCnVFdQnfhYGkPQF/<0;1>/*))#54uq36v8"
    DescriptorInfo.from_str(s)
    # assert descriptor_info.__dict__ == {}
