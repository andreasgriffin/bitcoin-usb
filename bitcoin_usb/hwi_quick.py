import importlib
import logging
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import bdkpython as bdk
import hwilib.commands as hwi_commands

from .device import bdknetwork_to_chain

logger = logging.getLogger(__name__)


class HWIQuick:
    """The issue with hwilib.commands.enumerate is that it needs to unlock all connected devices.
    However for simply listing the devices (without fingerprint), this isnt necessary.

    Even worse, if multiple USB devices are connected and the user is expecting to use
    device A, and hwi tries to init the client for device B, the user is confused, because he
    just sees a blocking UI and doesnt notice device B.

    In this class we therefore use hwilib, but mock the Client class, such that it doesnt
    need to unlock the device and just returns dummy values.

    To really access the device only "type" and "path" are important, which HWIQuick does get:
        hwi_commands.get_client(
            device_type=self.selected_device["type"],
            device_path=self.selected_device["path"],
            chain=bdknetwork_to_chain(self.network),
        ).
    """

    def __init__(self, network: bdk.Network) -> None:
        self.network = network

    @staticmethod
    def mock_bitbox02_enumerate():
        from hwilib.devices.bitbox02_lib.communication.bitbox_api_protocol import (
            BitBox02Edition,
        )

        imported_bitbox02 = importlib.import_module("hwilib.devices.bitbox02_lib.communication.devices")

        result = []
        for device_info in imported_bitbox02.get_any_bitbox02s():

            path = device_info["path"].decode()
            d_data: Dict[str, object] = {}

            d_data.update(
                {
                    "type": "bitbox02",
                    "path": path,
                    "model": {
                        BitBox02Edition.MULTI: "bitbox02_multi",
                        BitBox02Edition.BTCONLY: "bitbox02_btconly",
                    }[BitBox02Edition.BTCONLY],
                    "needs_pin_sent": False,
                    "needs_passphrase_sent": False,
                }
            )
            result.append(d_data)
        return result

    @patch("hwilib.devices.jade.JadeClient", new_callable=MagicMock)
    @patch("hwilib.devices.coldcard.ColdcardClient", new_callable=MagicMock)
    @patch("hwilib.devices.keepkey.KeepkeyClient")
    @patch("hwilib.devices.digitalbitbox.send_encrypt")
    @patch("hwilib.devices.digitalbitbox.DigitalbitboxClient")
    @patch("hwilib.devices.ledger.LedgerClient")
    @patch("hwilib.devices.trezor.TrezorClient")
    @patch("hwilib.devices.bitbox02.enumerate")
    def enumerate(
        self,
        bitbox02_enumerate,
        mock_trezor_client,
        mock_ledger_client,
        mock_digitalbitbox_client,
        mock_digitalbitbox_send_encrypt,
        mock_keepkey_client,
        mock_coldcard_client,
        mock_jade_client,
    ) -> List[Dict[str, Any]]:
        "This enumerates the devices without unlocking them. It cannot retrieve the fingerprint"
        allow_emulators = False
        devices = []

        mock_jade_instance = mock_jade_client.return_value
        mock_jade_instance.get_master_fingerprint.return_value = "mocked result"

        mock_coldcard_instance = mock_coldcard_client.return_value
        mock_coldcard_instance.get_master_fingerprint.return_value = "mocked result"

        # mock_keepkey_client
        mock_client_instance = mock_keepkey_client.return_value
        mock_client_instance.get_master_fingerprint.return_value = "mocked result"
        mock_client_instance.client = MagicMock(
            refresh_features=MagicMock(),
            features=MagicMock(
                vendor="keepkey",
                label="Mock KeepKey",
                unlocked=False,
                initialized=True,
                pin_protection=True,
                passphrase_protection=False,
            ),
        )

        # Configure the mock client
        mock_client_instance = mock_digitalbitbox_client.return_value
        mock_client_instance.get_master_fingerprint.return_value = "mocked result"
        mock_digitalbitbox_send_encrypt.return_value = {"fingerprint": "mocked result"}

        # Configure the mock LedgerClient
        mock_client_instance = mock_ledger_client.return_value
        mock_client_instance.get_master_fingerprint.return_value = MagicMock(hex=lambda: "mocked result")

        # Setup the mock TrezorClient
        mock_client_instance = mock_trezor_client.return_value
        mock_client_instance.get_master_fingerprint.return_value = MagicMock(hex=lambda: "mocked result")
        mock_client_instance.client.features = MagicMock(
            vendor="trezor",
            model="",
            label="Trezor",
            unlocked=False,
            pin_protection=True,
            passphrase_protection=False,
            initialized=True,
        )

        bitbox02_enumerate.return_value = self.mock_bitbox02_enumerate()

        devices = hwi_commands.enumerate(
            allow_emulators=allow_emulators, chain=bdknetwork_to_chain(self.network)
        )
        return devices
