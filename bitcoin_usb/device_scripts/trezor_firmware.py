"""
trezorlib.cli.firmware.update can stop/exit such, that it would halt the entire python 
program. Therefore I encapsulate it in this script, such that it can be called safely.
"""

import argparse
import sys

import trezorlib.cli
import trezorlib.cli.firmware

parser = argparse.ArgumentParser(description="Installs the trezor firmware")
parser.add_argument(
    "--path",
    required=True,
    type=str,
    help=f"The device path from HWI",
)
args = parser.parse_args()
path = args.path
# delete the arguments, because they are not intended for trezorlib.cli.firmware
sys.argv = sys.argv[:1]


connection = trezorlib.cli.TrezorConnection(
    path=path, session_id=None, passphrase_on_host=False, script=False
)


trezorlib.cli.firmware.update(obj=connection)
