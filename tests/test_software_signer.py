import logging
import bdkpython as bdk
import pytest
from hwilib.psbt import PSBT

from bitcoin_usb.software_signer import SoftwareSigner

# test seeds
# seed1: spider manual inform reject arch raccoon betray moon document across main build
# seed2: similar seek stock parent depart rug adjust acoustic oppose sell roast hockey
# seed3: debris yellow child maze hen lamp law venue pluck ketchup melody sick

logger = logging.getLogger(__name__)

network = bdk.Network.REGTEST


def test_single_sig_spend():
    seed = "spider manual inform reject arch raccoon betray moon document across main build"

    psbt = "cHNidP8BAHECAAAAAX+OrD5rcUUUsYNLBWdcJjYG8TD9cfqttrEuG2Xj8PFgAAAAAAD9////AvNJXQUAAAAAFgAU9RChTmc3g0aRPVXDW3Pn+4BpcnyAlpgAAAAAABYAFCre0yWobi1cdShVshiOIFBiJzTDdgAAAE8BBDWHzwMyFoPCgAAAAJGLoVloEn3xJ2mtPtKTWFKeElFncZVq25u2pPBXiYyJA7ghwtM8sm2iyDZJuQsPpkPzv/Mz7WoCeW8ySg/cJZw4EHyF8rVUAACAAQAAgAAAAIAAAQBxAgAAAAHzye6Jjq/OfTShvE1mK4mPHq46TnLWXXl/Dst7HVD2CgAAAAAA/f///wIA4fUFAAAAABYAFI6GwbSN5egsC6wjpye0G9z6emxhcxAQJAEAAAAWABSdDWCaRKCzjBdtdrhQmWCAuiY/CAAAAAABAR8A4fUFAAAAABYAFI6GwbSN5egsC6wjpye0G9z6emxhAQMEAQAAACIGAmwUkzrL/GENve6WmL8kg0lNdhSHdIKe4dJjuO281HCZGHyF8rVUAACAAQAAgAAAAIAAAAAAAAAAAAAiAgNdIY795pswZFA83q0cM9XbgmXl8MU29aseHqtv7+wGzBh8hfK1VAAAgAEAAIAAAACAAQAAAAAAAAAAIgIDJE38dFQK12Q+UlcjOn+X/fHGcm84ablxHKI56Qr6t+0YfIXytVQAAIABAACAAAAAgAAAAAABAAAAAA=="
    descriptor = "wpkh([7c85f2b5/84'/1'/0']tpubDCPkYWRWsTRZji1938hvWzdDsfQ39aasHz47s3htaKyYSHGdZBoNynBzwQsFS4xn4X4basMr1qL3DcPbjhcVNCzLzGhLoZixu2CAke9Q3hK/0/*)"
    change_descriptor = "wpkh([7c85f2b5/84'/1'/0']tpubDCPkYWRWsTRZji1938hvWzdDsfQ39aasHz47s3htaKyYSHGdZBoNynBzwQsFS4xn4X4basMr1qL3DcPbjhcVNCzLzGhLoZixu2CAke9Q3hK/1/*)"
    software_signer = SoftwareSigner(
        mnemonic=seed,
        network=network,
        receive_descriptor=descriptor,
        change_descriptor=change_descriptor,
    )
    signed_psbt = software_signer.sign_psbt(bdk.Psbt(psbt))

    assert signed_psbt
    assert signed_psbt.extract_tx()
    logger.info(signed_psbt)

    missing_prev_tx = PSBT()
    missing_prev_tx.deserialize(psbt)
    missing_prev_tx.inputs[0].non_witness_utxo = None
    signed_without_prev_tx = software_signer.sign_psbt(bdk.Psbt(missing_prev_tx.serialize()))
    assert signed_without_prev_tx
    assert signed_without_prev_tx.extract_tx()

    missing_prev_tx.inputs[0].witness_utxo = None
    with pytest.raises(bdk.InputSignError.MissingSpendUtxo):
        software_signer.sign_psbt(bdk.Psbt(missing_prev_tx.serialize()))

    unusual_sighash = PSBT()
    unusual_sighash.deserialize(psbt)
    unusual_sighash.inputs[0].sighash = 0x81
    unusual_signed = software_signer.sign_psbt(bdk.Psbt(unusual_sighash.serialize()))
    assert unusual_signed
    unusual_result = PSBT()
    unusual_result.deserialize(unusual_signed.serialize())
    assert unusual_result.inputs[0].final_script_witness.scriptWitness.stack[0][-1] == 0x81

    unrelated_signer = SoftwareSigner(
        mnemonic="similar seek stock parent depart rug adjust acoustic oppose sell roast hockey",
        network=network,
        receive_descriptor=descriptor,
        change_descriptor=change_descriptor,
    )
    assert unrelated_signer.sign_psbt(bdk.Psbt(psbt)) is None


def test_single_multisig_sign():
    seed = "spider manual inform reject arch raccoon betray moon document across main build"

    descriptor = "wsh(sortedmulti(2,[7c85f2b5/48'/1'/0'/2']tpubDEBYeoKBCaY1h6353GCojAoPdi7GGz4JYhyac8StrxBWKZCb5nQQQJCFndXFmFGgakmPxS3zQkkCxzKGuLGBKhgfL96jrc6L3rn1D5bAhjo/0/*,[34be20d9/48'/1'/0'/2']tpubDEGiMrEBpyW7ebPDipDBwgxi4Ct4VqDApRcDEZy6uT8HoE5jUduJiXH7axkuQdcf7ZGamBbng7Ym3MPwLHqkugswt1uCParZBGyGsfEZ7PQ/0/*,[3b8adfc3/48'/1'/0'/2']tpubDEmjAPbjr9QfDidVmgSGdK6JYXiFy1xw9pVmXXSbZxa8qz2ixtZhaRyLdMS3wwECPao4PRC4dGWXnpwnzGUAaVewbW9VtkYaMg4neeTFLm6/0/*))"
    change_descriptor = "wsh(sortedmulti(2,[7c85f2b5/48'/1'/0'/2']tpubDEBYeoKBCaY1h6353GCojAoPdi7GGz4JYhyac8StrxBWKZCb5nQQQJCFndXFmFGgakmPxS3zQkkCxzKGuLGBKhgfL96jrc6L3rn1D5bAhjo/1/*,[34be20d9/48'/1'/0'/2']tpubDEGiMrEBpyW7ebPDipDBwgxi4Ct4VqDApRcDEZy6uT8HoE5jUduJiXH7axkuQdcf7ZGamBbng7Ym3MPwLHqkugswt1uCParZBGyGsfEZ7PQ/1/*,[3b8adfc3/48'/1'/0'/2']tpubDEmjAPbjr9QfDidVmgSGdK6JYXiFy1xw9pVmXXSbZxa8qz2ixtZhaRyLdMS3wwECPao4PRC4dGWXnpwnzGUAaVewbW9VtkYaMg4neeTFLm6/1/*))"

    psbt = "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"

    software_signer = SoftwareSigner(
        mnemonic=seed,
        network=network,
        receive_descriptor=descriptor,
        change_descriptor=change_descriptor,
    )
    signed_psbt = software_signer.sign_psbt(bdk.Psbt(psbt))

    assert signed_psbt
    partial_psbt = PSBT()
    partial_psbt.deserialize(signed_psbt.serialize())
    assert len(partial_psbt.inputs[0].partial_sigs) == 1
    logger.info(signed_psbt.serialize())

    # now sign with 2. key
    seed = "similar seek stock parent depart rug adjust acoustic oppose sell roast hockey"

    psbt = signed_psbt.serialize()

    software_signer = SoftwareSigner(
        mnemonic=seed,
        network=network,
        receive_descriptor=descriptor,
        change_descriptor=change_descriptor,
    )
    signed_psbt = software_signer.sign_psbt(bdk.Psbt(psbt))

    assert signed_psbt
    assert signed_psbt.extract_tx()
