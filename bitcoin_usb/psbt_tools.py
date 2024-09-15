import logging
from typing import Dict, Optional, Tuple

import bdkpython as bdk

logger = logging.getLogger(__name__)

from bitcointx import select_chain_params
from bitcointx.core.key import BIP32Path
from bitcointx.core.psbt import (
    PartiallySignedTransaction as TXPartiallySignedTransaction,
)
from bitcointx.core.psbt import PSBT_KeyDerivationInfo
from bitcointx.wallet import CCoinExtPubKey


class PSBTTools:
    @staticmethod
    def finalize(psbt: bdk.PartiallySignedTransaction) -> Optional[bdk.Transaction]:
        psbt_tx: TXPartiallySignedTransaction = TXPartiallySignedTransaction.from_base64(psbt.serialize())
        # this trys to finalize the tx
        try:
            psbt_tx.extract_transaction()
            if psbt_tx.is_final():
                return bdk.Transaction(psbt_tx.extract_transaction().serialize())
            return None
        except:
            return None

    @staticmethod
    def add_global_xpub_dict_to_psbt(
        psbt: bdk.PartiallySignedTransaction, global_xpub: Dict[str, Tuple[str, str]], network: bdk.Network
    ) -> bdk.PartiallySignedTransaction:
        # Select network parameters
        network_params = {
            bdk.Network.BITCOIN: "bitcoin",
            bdk.Network.TESTNET: "bitcoin/testnet",
            bdk.Network.REGTEST: "bitcoin/regtest",
            bdk.Network.SIGNET: "bitcoin/signet",
        }
        select_chain_params(network_params.get(network, "bitcoin"))

        tx_psbt = TXPartiallySignedTransaction.from_base64(psbt.serialize())

        for xpub_str, (fingerprint, path) in global_xpub.items():
            xpub = CCoinExtPubKey(xpub_str)
            tx_psbt.xpubs[xpub] = PSBT_KeyDerivationInfo(bytes.fromhex(fingerprint), BIP32Path(path))

        new_psbt = bdk.PartiallySignedTransaction(tx_psbt.to_base64())
        # just a check that NOTHING evil has happened here
        assert new_psbt.extract_tx().txid() == psbt.extract_tx().txid()
        return new_psbt
