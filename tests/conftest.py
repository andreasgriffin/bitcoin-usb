import os
from collections.abc import Iterator
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def disable_real_hardware_access(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """
    Keep the default test suite hardware-independent.

    Set BITCOIN_USB_TEST_REAL_HWI=1 to run tests against real connected devices.
    """
    if os.environ.get("BITCOIN_USB_TEST_REAL_HWI") == "1":
        yield
        return

    def fake_enumerate(allow_emulators: bool = False, chain: Any = None) -> list[dict[str, Any]]:
        _ = allow_emulators
        _ = chain
        return []

    def fake_get_client(
        device_type: str,
        device_path: str,
        password: str = "",
        expert: bool = False,
        chain: Any = None,
        **kwargs: Any,
    ) -> Any:
        _ = device_type
        _ = device_path
        _ = password
        _ = expert
        _ = chain
        _ = kwargs
        raise RuntimeError(
            "Real hardware access is disabled during tests. "
            "Set BITCOIN_USB_TEST_REAL_HWI=1 to enable integration behavior."
        )

    monkeypatch.setattr("hwilib.commands.enumerate", fake_enumerate)
    monkeypatch.setattr("hwilib.commands.get_client", fake_get_client)
    yield
