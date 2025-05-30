import bdkpython as bdk

from bitcoin_usb.address_types import bdk, logger
from bitcoin_usb.software_signer import SoftwareSigner

# test seeds
# seed1: spider manual inform reject arch raccoon betray moon document across main build
# seed2: similar seek stock parent depart rug adjust acoustic oppose sell roast hockey
# seed3: debris yellow child maze hen lamp law venue pluck ketchup melody sick


network = bdk.Network.REGTEST


def test_single_sig_spend():
    seed = "spider manual inform reject arch raccoon betray moon document across main build"

    psbt = "cHNidP8BAHECAAAAAX+OrD5rcUUUsYNLBWdcJjYG8TD9cfqttrEuG2Xj8PFgAAAAAAD9////AvNJXQUAAAAAFgAU9RChTmc3g0aRPVXDW3Pn+4BpcnyAlpgAAAAAABYAFCre0yWobi1cdShVshiOIFBiJzTDdgAAAE8BBDWHzwMyFoPCgAAAAJGLoVloEn3xJ2mtPtKTWFKeElFncZVq25u2pPBXiYyJA7ghwtM8sm2iyDZJuQsPpkPzv/Mz7WoCeW8ySg/cJZw4EHyF8rVUAACAAQAAgAAAAIAAAQBxAgAAAAHzye6Jjq/OfTShvE1mK4mPHq46TnLWXXl/Dst7HVD2CgAAAAAA/f///wIA4fUFAAAAABYAFI6GwbSN5egsC6wjpye0G9z6emxhcxAQJAEAAAAWABSdDWCaRKCzjBdtdrhQmWCAuiY/CAAAAAABAR8A4fUFAAAAABYAFI6GwbSN5egsC6wjpye0G9z6emxhAQMEAQAAACIGAmwUkzrL/GENve6WmL8kg0lNdhSHdIKe4dJjuO281HCZGHyF8rVUAACAAQAAgAAAAIAAAAAAAAAAAAAiAgNdIY795pswZFA83q0cM9XbgmXl8MU29aseHqtv7+wGzBh8hfK1VAAAgAEAAIAAAACAAQAAAAAAAAAAIgIDJE38dFQK12Q+UlcjOn+X/fHGcm84ablxHKI56Qr6t+0YfIXytVQAAIABAACAAAAAgAAAAAABAAAAAA=="
    descriptor = "wpkh([7c85f2b5/84'/1'/0']tpubDCPkYWRWsTRZji1938hvWzdDsfQ39aasHz47s3htaKyYSHGdZBoNynBzwQsFS4xn4X4basMr1qL3DcPbjhcVNCzLzGhLoZixu2CAke9Q3hK/0/*)"
    change_descriptor = "wpkh([7c85f2b5/84'/1'/0']tpubDCPkYWRWsTRZji1938hvWzdDsfQ39aasHz47s3htaKyYSHGdZBoNynBzwQsFS4xn4X4basMr1qL3DcPbjhcVNCzLzGhLoZixu2CAke9Q3hK/1/*)"
    software_signer = SoftwareSigner(
        mnemonic=seed, network=network, receive_descriptor=descriptor, change_descriptor=change_descriptor
    )
    signed_psbt = software_signer.sign_psbt(bdk.Psbt(psbt))

    assert signed_psbt
    assert (
        signed_psbt.serialize()
        == "cHNidP8BAHECAAAAAX+OrD5rcUUUsYNLBWdcJjYG8TD9cfqttrEuG2Xj8PFgAAAAAAD9////AvNJXQUAAAAAFgAU9RChTmc3g0aRPVXDW3Pn+4BpcnyAlpgAAAAAABYAFCre0yWobi1cdShVshiOIFBiJzTDdgAAAE8BBDWHzwMyFoPCgAAAAJGLoVloEn3xJ2mtPtKTWFKeElFncZVq25u2pPBXiYyJA7ghwtM8sm2iyDZJuQsPpkPzv/Mz7WoCeW8ySg/cJZw4EHyF8rVUAACAAQAAgAAAAIAAAQBxAgAAAAHzye6Jjq/OfTShvE1mK4mPHq46TnLWXXl/Dst7HVD2CgAAAAAA/f///wIA4fUFAAAAABYAFI6GwbSN5egsC6wjpye0G9z6emxhcxAQJAEAAAAWABSdDWCaRKCzjBdtdrhQmWCAuiY/CAAAAAABAR8A4fUFAAAAABYAFI6GwbSN5egsC6wjpye0G9z6emxhAQhrAkcwRAIgbZS9PecHX4GhPQCdcYv4mbXkuKmypAlQSDCDmY8k0AECIGA3WVj1VfZF2xSdMJnFO/CUXMOyfqG2tvlNMZoRVusjASECbBSTOsv8YQ297paYvySDSU12FId0gp7h0mO47bzUcJkAAAA="
    )
    logger.info(signed_psbt)


## bdk wallet.sign cannot sign if only 1 of the xpriv in a multisig descritpors is present


def test_single_multisig_sign():
    seed = "spider manual inform reject arch raccoon betray moon document across main build"

    descriptor = "wsh(sortedmulti(2,[7c85f2b5/48'/1'/0'/2']tpubDEBYeoKBCaY1h6353GCojAoPdi7GGz4JYhyac8StrxBWKZCb5nQQQJCFndXFmFGgakmPxS3zQkkCxzKGuLGBKhgfL96jrc6L3rn1D5bAhjo/0/*,[34be20d9/48'/1'/0'/2']tpubDEGiMrEBpyW7ebPDipDBwgxi4Ct4VqDApRcDEZy6uT8HoE5jUduJiXH7axkuQdcf7ZGamBbng7Ym3MPwLHqkugswt1uCParZBGyGsfEZ7PQ/0/*,[3b8adfc3/48'/1'/0'/2']tpubDEmjAPbjr9QfDidVmgSGdK6JYXiFy1xw9pVmXXSbZxa8qz2ixtZhaRyLdMS3wwECPao4PRC4dGWXnpwnzGUAaVewbW9VtkYaMg4neeTFLm6/0/*))"
    change_descriptor = "wsh(sortedmulti(2,[7c85f2b5/48'/1'/0'/2']tpubDEBYeoKBCaY1h6353GCojAoPdi7GGz4JYhyac8StrxBWKZCb5nQQQJCFndXFmFGgakmPxS3zQkkCxzKGuLGBKhgfL96jrc6L3rn1D5bAhjo/1/*,[34be20d9/48'/1'/0'/2']tpubDEGiMrEBpyW7ebPDipDBwgxi4Ct4VqDApRcDEZy6uT8HoE5jUduJiXH7axkuQdcf7ZGamBbng7Ym3MPwLHqkugswt1uCParZBGyGsfEZ7PQ/1/*,[3b8adfc3/48'/1'/0'/2']tpubDEmjAPbjr9QfDidVmgSGdK6JYXiFy1xw9pVmXXSbZxa8qz2ixtZhaRyLdMS3wwECPao4PRC4dGWXnpwnzGUAaVewbW9VtkYaMg4neeTFLm6/1/*))"

    psbt = "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"

    software_signer = SoftwareSigner(
        mnemonic=seed, network=network, receive_descriptor=descriptor, change_descriptor=change_descriptor
    )
    signed_psbt = software_signer.sign_psbt(bdk.Psbt(psbt))

    assert signed_psbt
    assert (
        signed_psbt.serialize()
        == "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"
    )
    logger.info(signed_psbt.serialize())

    # now sign with 2. key
    seed = "similar seek stock parent depart rug adjust acoustic oppose sell roast hockey"

    psbt = signed_psbt.serialize()

    software_signer = SoftwareSigner(
        mnemonic=seed, network=network, receive_descriptor=descriptor, change_descriptor=change_descriptor
    )
    signed_psbt = software_signer.sign_psbt(bdk.Psbt(psbt))

    assert signed_psbt
    assert (
        bytes(signed_psbt.extract_tx().serialize()).hex()
        == "0200000000010128c8e3ab7c31d11bb2265f54f922699dc9182ed89b14f23199bbe040ddd86d420000000000fdffffff02fe89980000000000220020723cf643b3c2e85d215128afce16551230bd8159b549169512684d70dc1d2baeb80b000000000000220020b2a19f1275b630ae74a74230bd3d05c790e0ce40f7a7df1f700c5cdca3e64906040047304402201477c2de8e9c344e73180cbc7a9e80cfd30ec80c086699ffb7df7760a5d6dffd022063695caa8ced6ab840e75d7d0d976d71264d3ffea0a8672fc6c6f22580366833014730440220786b0e7aba74b314ffb6fda3230a8ef061d39599d3f76e2232840dc43ba4f28c02203e031d7fbee4173252955b5ba39c59b6f93c1414aed984eec855a1a341af24ea01695221020e2ee7198d38999ec6ad8aefe406e8ab1c9fae389ee4c73852ee122680f780d221023a430c92212723fd7fa476fd7d82d0cf68cd7073f156af2bc7c72a361ffd361b21029fa5fe0e44c875a546e712d19622a277a1b003f3f7c6334fd2c576a2f884d15c53ae050c0000"
    )
