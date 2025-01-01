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
    def select_bitcointx_network(network: bdk.Network):
        network_params = {
            bdk.Network.BITCOIN: "bitcoin",
            bdk.Network.TESTNET: "bitcoin/testnet",
            bdk.Network.REGTEST: "bitcoin/regtest",
            bdk.Network.SIGNET: "bitcoin/signet",
        }
        select_chain_params(network_params.get(network, "bitcoin"))

    @staticmethod
    def finalize(psbt: bdk.PartiallySignedTransaction, network: bdk.Network) -> Optional[bdk.Transaction]:
        PSBTTools.select_bitcointx_network(network)
        try:
            psbt_tx: TXPartiallySignedTransaction = TXPartiallySignedTransaction.from_base64(psbt.serialize())
            # this trys to finalize the tx
            psbt_tx.extract_transaction()
            if psbt_tx.is_final():
                return bdk.Transaction(list(psbt_tx.extract_transaction().serialize()))
            return None
        except:
            return None

    @staticmethod
    def add_global_xpub_dict_to_psbt(
        psbt: bdk.PartiallySignedTransaction, global_xpub: Dict[str, Tuple[str, str]], network: bdk.Network
    ) -> bdk.PartiallySignedTransaction:
        PSBTTools.select_bitcointx_network(network)

        tx_psbt = TXPartiallySignedTransaction.from_base64(psbt.serialize())

        for xpub_str, (fingerprint, path) in global_xpub.items():
            xpub = CCoinExtPubKey(xpub_str)
            tx_psbt.xpubs[xpub] = PSBT_KeyDerivationInfo(bytes.fromhex(fingerprint), BIP32Path(path))

        new_psbt = bdk.PartiallySignedTransaction(tx_psbt.to_base64())
        # just a check that NOTHING evil has happened here
        assert new_psbt.extract_tx().txid() == psbt.extract_tx().txid()
        return new_psbt
