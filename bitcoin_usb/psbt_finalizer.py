import logging
from typing import Optional

import bdkpython as bdk

logger = logging.getLogger(__name__)

from bitcointx.core.psbt import (
    PartiallySignedTransaction as TXPartiallySignedTransaction,
)


class PSBTFinalizer:
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
