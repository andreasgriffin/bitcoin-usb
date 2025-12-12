import asyncio
import logging
import subprocess
import sys
from collections.abc import Callable
from typing import TypeVar

from bitcoin_safe_lib.async_tools.loop_in_thread import LoopInThread
from PyQt6.QtCore import QEventLoop

logger = logging.getLogger(__name__)


T = TypeVar("T")


def run_script(script_name, args: list[str]):
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


def run_device_task(loop_in_thread: LoopInThread | None, task: Callable[[], T]) -> T | None:
    if not loop_in_thread:
        return task()

    loop = QEventLoop()
    done = False
    result: list[T] = []
    caught: list[BaseException] = []

    def _finish(res: T | None = None):
        nonlocal done
        if done:
            return
        done = True
        if res is not None:
            result.append(res)
        if loop.isRunning():
            loop.quit()

    def _on_error(exc_info):
        if exc_info and exc_info[1]:
            caught.append(exc_info[1])
        _finish()

    loop_in_thread.run_task(
        asyncio.to_thread(task),
        on_success=_finish,
        on_error=_on_error,
        on_done=_finish,
    )

    loop.exec()

    if caught:
        raise caught[0]

    return result[0] if result else None
