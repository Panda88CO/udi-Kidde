"""Mock infrastructure for running udi-Kidde tests without external dependencies."""

from __future__ import annotations

import sys
import types
from typing import Any, Callable, Dict, List, Optional


class MockLogger:
    def __init__(self) -> None:
        self.logs: list[tuple[str, str]] = []

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.logs.append(("DEBUG", msg % args if args else msg))

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.logs.append(("INFO", msg % args if args else msg))

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.logs.append(("WARNING", msg % args if args else msg))

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.logs.append(("ERROR", msg % args if args else msg))

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.logs.append(("EXCEPTION", msg % args if args else msg))


class MockCustom:
    def __init__(self, polyglot: Any, key: str) -> None:
        self.polyglot = polyglot
        self.key = key
        self.data: dict[str, Any] = {}

    def load(self, data: dict[str, Any]) -> None:
        self.data = dict(data or {})

    def __getitem__(self, key: str) -> Any:
        return self.data.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value


class MockNotices(dict):
    def clear(self) -> None:
        super().clear()

    def delete(self, key: str) -> None:
        self.pop(key, None)


class MockBaseNode:
    """Mock implementation of udi_interface.Node."""

    def __init__(self, polyglot: Any, primary: str, address: str, name: str) -> None:
        self.poly = polyglot
        self.primary = primary
        self.address = address
        self.name = name
        self.drivers_reported: dict[str, Any] = {}
        self.driver_uoms_reported: dict[str, Optional[int]] = {}
        self.commands_reported: list[tuple[str, Any]] = []
        self.added = False

    def setDriver(
        self,
        driver: str,
        value: Any,
        report: bool = True,
        force: bool = False,
        uom: Optional[int] = None,
    ) -> None:
        self.drivers_reported[driver] = value
        if uom is not None:
            self.driver_uoms_reported[driver] = uom

    def getDriver(self, driver: str) -> Any:
        return self.drivers_reported.get(driver, 0)

    def reportCmd(self, command: str, value: Any = None, uom: Optional[int] = None) -> None:
        self.commands_reported.append((command, value))


class MockPolyglot:
    """Mock implementation of udi_interface.Interface."""

    START = "start"
    STOP = "stop"
    POLL = "poll"
    CUSTOMPARAMS = "customparams"
    CUSTOMDATA = "customdata"
    CONFIGDONE = "configdone"
    ADDNODEDONE = "addnodedone"
    LOGLEVEL = "loglevel"
    DISCOVER = "discover"

    def __init__(self) -> None:
        self.subscriptions: dict[str, list[Callable[..., Any]]] = {}
        self.nodes: dict[str, Any] = {}
        self.Notices = MockNotices()
        self.profile_payload: Optional[dict[str, Any]] = None
        self.ready_called = False

    def subscribe(self, event: str, callback: Callable[..., Any], *args: Any) -> None:
        self.subscriptions.setdefault(event, []).append(callback)

    def ready(self) -> None:
        self.ready_called = True

    def addNode(self, node: Any, conn_status: Optional[str] = None, rename: bool = False) -> None:
        node.added = True
        self.nodes[node.address] = node

    def delNode(self, address: str) -> None:
        self.nodes.pop(address, None)

    def updateJsonProfile(self, payload: dict[str, Any], options: Optional[dict[str, Any]] = None) -> None:
        self.profile_payload = payload

    def getValidAddress(self, name: str) -> str:
        # Standard Polyglot address sanitization approximation
        valid = "".join(c for c in name.lower() if c.isalnum() or c == "_")
        return valid[:14]

    def getValidName(self, name: str) -> str:
        return str(name)[:32]


def setup_mocks() -> None:
    """Inject mock modules into sys.modules if not present."""
    if "udi_interface" not in sys.modules:
        mock_udi = types.ModuleType("udi_interface")
        mock_udi.LOGGER = MockLogger()
        mock_udi.Custom = MockCustom
        mock_udi.Node = MockBaseNode
        mock_udi.Interface = MockPolyglot
        sys.modules["udi_interface"] = mock_udi

    if "kidde_homesafe" not in sys.modules:
        mock_kh = types.ModuleType("kidde_homesafe")
        mock_kh.KiddeClient = object
        mock_kh.KiddeClientAuthError = type("KiddeClientAuthError", (Exception,), {})

        class MockKiddeCommand:
            IDENTIFY = 1
            IDENTIFYCANCEL = 2
            TEST = 3
            HUSH = 4

        mock_kh.KiddeCommand = MockKiddeCommand
        sys.modules["kidde_homesafe"] = mock_kh

