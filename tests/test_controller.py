"""Tests for KiddeController lifecycle, polling, TIME behavior, and device reconciliation."""

from __future__ import annotations

import types
import unittest
try:
    from tests.conftest_mock import MockPolyglot, setup_mocks
except ImportError:
    from conftest_mock import MockPolyglot, setup_mocks

setup_mocks()

import nodes


class TestKiddeController(unittest.TestCase):
    """Verify KiddeController operational behavior and TIME constraints."""

    def setUp(self) -> None:
        self.poly = MockPolyglot()
        self.controller = nodes.KiddeController(self.poly, "setup", "setup", "Kidde Monitors")
        # Provide valid credentials
        self.controller.config = types.SimpleNamespace(
            email="user@example.com",
            password="secretpassword",
            temp_unit="F",
        )
        self.controller._has_valid_params = True
        self.controller._config_done = True
        self.controller._controller_node_added = True

    def test_initial_state_and_time_defaults(self) -> None:
        """Controller must initialize last_update to 0 and not report TIME prematurely."""
        self.assertEqual(self.controller.last_update, 0)
        self.assertNotIn("TIME", self.controller.drivers_reported)

        # Drivers array declaration must initialize TIME to 0
        time_driver = next(d for d in nodes.KiddeController.drivers if d["driver"] == "TIME")
        self.assertEqual(time_driver["value"], 0, "Initial TIME driver value must be 0")

    def test_start_does_not_update_time(self) -> None:
        """Calling start() must not touch TIME before data is received."""
        self.controller.start()
        self.assertTrue(self.controller._started)
        self.assertNotIn("TIME", self.controller.drivers_reported)

    def test_short_poll_toggles_heartbeat_without_updating_time(self) -> None:
        """shortPoll must toggle DON/DOF heartbeat and NEVER update TIME."""
        initial_time_calls = "TIME" in self.controller.drivers_reported

        # 1st shortPoll
        self.controller.poll("shortPoll")
        self.assertEqual(self.controller.commands_reported[-1][0], "DON")
        self.assertEqual("TIME" in self.controller.drivers_reported, initial_time_calls)

        # 2nd shortPoll
        self.controller.poll("shortPoll")
        self.assertEqual(self.controller.commands_reported[-1][0], "DOF")
        self.assertEqual("TIME" in self.controller.drivers_reported, initial_time_calls)

    def test_refresh_failure_does_not_update_time(self) -> None:
        """When Kidde refresh returns None or fails, TIME must NOT be set."""
        self.controller.adapter.refresh = lambda *a, **k: None

        self.controller._refresh_status()

        self.assertEqual(self.controller.online, 0)
        self.assertEqual(self.controller.drivers_reported.get("ST"), 0)
        self.assertEqual(self.controller.drivers_reported.get("GV1"), 0)
        self.assertIn("refresh", self.controller.poly.Notices)
        self.assertNotIn("TIME", self.controller.drivers_reported, "TIME must not be set on failure")
        self.assertEqual(self.controller.last_update, 0)

    def test_refresh_success_updates_time_and_drivers(self) -> None:
        """When Kidde refresh succeeds, TIME is updated to a positive unix timestamp."""
        fake_devices = {
            "1001": {
                "model": "wifidetector",
                "capabilities": ["smoke"],
                "last_seen": "2026-10-04T15:00:00",
            }
        }
        self.controller.adapter.refresh = lambda *a, **k: {
            "num_alarms": 0,
            "devices": fake_devices,
        }

        self.controller._refresh_status()

        self.assertEqual(self.controller.online, 1)
        self.assertEqual(self.controller.drivers_reported.get("ST"), 1)
        self.assertEqual(self.controller.drivers_reported.get("GV1"), 1)
        self.assertNotIn("refresh", self.controller.poly.Notices)
        self.assertIn("TIME", self.controller.drivers_reported)

        recorded_time = self.controller.drivers_reported["TIME"]
        self.assertGreater(recorded_time, 0)
        self.assertEqual(self.controller.last_update, recorded_time)

    def test_subsequent_failure_preserves_previous_time(self) -> None:
        """If a subsequent refresh fails after a success, TIME is not overwritten."""
        # 1. Successful refresh
        self.controller.adapter.refresh = lambda *a, **k: {
            "num_alarms": 0,
            "devices": {},
        }
        self.controller._refresh_status()
        first_time = self.controller.last_update
        self.assertGreater(first_time, 0)

        # Clear reported driver dict to detect any new calls
        self.controller.drivers_reported.clear()

        # 2. Failed refresh
        self.controller.adapter.refresh = lambda *a, **k: None
        self.controller._refresh_status()

        self.assertEqual(self.controller.online, 0)
        self.assertEqual(self.controller.drivers_reported.get("ST"), 0)
        self.assertEqual(self.controller.drivers_reported.get("GV1"), 0)
        self.assertNotIn("TIME", self.controller.drivers_reported, "TIME must not be touched on failure")
        self.assertEqual(self.controller.last_update, first_time, "last_update must remain unchanged")

    def test_reconcile_nodes_creates_and_removes_children(self) -> None:
        """Child nodes are created on discovery and removed when no longer reported."""
        devices = {
            "101": {
                "model": "wifidetector",
                "capabilities": ["smoke"],
                "label": "Hallway Smoke",
            },
            "102": {
                "model": "cowifidetector",
                "capabilities": ["co"],
                "label": "Kitchen CO",
            },
        }

        self.controller._reconcile_nodes(devices)
        self.assertEqual(len(self.controller._alarm_nodes), 2)
        self.assertIn(101, self.controller._alarm_nodes)
        self.assertIn(102, self.controller._alarm_nodes)

        # 101 has smoke only -> bitmask 4 -> KIDDEALARM4
        self.assertEqual(self.controller._alarm_nodes[101].id, "KIDDEALARM4")
        # 102 has co only -> bitmask 2 -> KIDDEALARM2
        self.assertEqual(self.controller._alarm_nodes[102].id, "KIDDEALARM2")

        # Now remove 102 from device list
        devices_reduced = {
            "101": devices["101"],
        }
        self.controller._reconcile_nodes(devices_reduced)
        self.assertEqual(len(self.controller._alarm_nodes), 1)
        self.assertIn(101, self.controller._alarm_nodes)
        self.assertNotIn(102, self.controller._alarm_nodes)


if __name__ == "__main__":
    unittest.main()
