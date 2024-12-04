import logging
import subprocess
import sys
from typing import List

logger = logging.getLogger(__name__)


def run_script(script_name, args: List[str]):
    # Run the script using the same Python interpreter that's running this script
    process = subprocess.Popen(
        [sys.executable, script_name] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,  # Ensures output is returned as strings
    )

    # Wait for the process to complete and get output and errors
    stdout, stderr = process.communicate()

    # Check if the process has exited with a non-zero exit code
    if process.returncode != 0:
        print(f"Error running script {script_name}: {stderr}")
    else:
        print(f"Script output: {stdout}")

    return stdout, stderr
