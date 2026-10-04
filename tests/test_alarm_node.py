"""Tests for KiddeAlarmNode capabilities, driver parsing, TIME guard, and commands."""

from __future__ import annotations

import types
import unittest
try:
    from tests.conftest_mock import MockPolyglot, setup_mocks
except ImportError:
    from conftest_mock import MockPolyglot, setup_mocks

setup_mocks()

import nodes


class TestAlarmNode(unittest.TestCase):
    """Verify KiddeAlarmNode nodedef logic, telemetry mapping, and commands."""

    def setUp(self) -> None:
        self.poly = MockPolyglot()

    def test_alarm_nodedef_id_bitmask(self) -> None:
        """Verify the 8 bitmask combinations produce KIDDEALARM0..7 without underscores."""
        expected = {
            (False, False, False): "KIDDEALARM0",
            (False, False, True):  "KIDDEALARM1",
            (False, True,  False): "KIDDEALARM2",
            (False, True,  True):  "KIDDEALARM3",
            (True,  False, False): "KIDDEALARM4",
            (True,  False, True):  "KIDDEALARM5",
            (True,  True,  False): "KIDDEALARM6",
            (True,  True,  True):  "KIDDEALARM7",
        }
        for (smoke, co, iaq), expected_id in expected.items():
            actual = nodes._alarm_nodedef_id(smoke, co, iaq)
            self.assertEqual(actual, expected_id)
            self.assertTrue(actual.isupper())
            self.assertNotIn("_", actual)

    def test_device_capability_deduction(self) -> None:
        """Capabilities extracted from list, model name, or device attributes."""
        # Explicit list
        caps1 = nodes._device_capabilities({"capabilities": ["smoke", "co"]})
        self.assertEqual(caps1, (True, True, False))

        # Model fallback for IAQ
        caps2 = nodes._device_capabilities({"model": "wifiiaqdetector", "capabilities": ["smoke"]})
        self.assertEqual(caps2, (True, False, True))

        # Key-based fallback
        caps3 = nodes._device_capabilities({"smoke_alarm": False, "co_alarm": False})
        self.assertEqual(caps3, (True, True, False))

    def test_alarm_onset_and_clearance_commands(self) -> None:
        """Reporting DON on alarm onset and DOF on alarm clearance."""
        node = nodes.KiddeAlarmNode(
            self.poly, "setup", "d101", "Alarm 101",
            location_id=1, device_id=101,
            supports_smoke=True, supports_co=True, supports_iaq=False,
        )

        # Initial normal state
        node.update_from_device({"smoke_alarm": False, "co_alarm": False})
        self.assertEqual(node.drivers_reported.get("ST"), 0)
        self.assertEqual(len(node.commands_reported), 0)

        # Alarm onset -> reports DON
        node.update_from_device({"smoke_alarm": True, "co_alarm": False})
        self.assertEqual(node.drivers_reported.get("ST"), 1)
        self.assertEqual(node.commands_reported[-1][0], "DON")

        # Ongoing alarm -> no redundant DON
        prev_cmds_len = len(node.commands_reported)
        node.update_from_device({"smoke_alarm": True, "co_alarm": False})
        self.assertEqual(len(node.commands_reported), prev_cmds_len)

        # Alarm cleared -> reports DOF
        node.update_from_device({"smoke_alarm": False, "co_alarm": False})
        self.assertEqual(node.drivers_reported.get("ST"), 0)
        self.assertEqual(node.commands_reported[-1][0], "DOF")

    def test_time_only_updates_on_valid_last_seen(self) -> None:
        """TIME driver only updates when a valid timestamp is present; 0 or missing does not wipe it."""
        node = nodes.KiddeAlarmNode(
            self.poly, "setup", "d101", "Alarm 101",
            location_id=1, device_id=101,
            supports_smoke=True, supports_co=False, supports_iaq=False,
        )

        # Missing or empty last_seen -> TIME not reported
        node.update_from_device({"last_seen": None})
        self.assertNotIn("TIME", node.drivers_reported)

        # Invalid string -> TIME not reported
        node.update_from_device({"last_seen": "not-a-timestamp"})
        self.assertNotIn("TIME", node.drivers_reported)

        # Valid ISO timestamp -> TIME reported
        node.update_from_device({"last_seen": "2026-10-04T12:30:00"})
        self.assertIn("TIME", node.drivers_reported)
        saved_time = node.drivers_reported["TIME"]
        self.assertGreater(saved_time, 0)

        # Subsequent payload with missing last_seen does NOT overwrite saved_time with 0
        node.update_from_device({"last_seen": ""})
        self.assertEqual(node.drivers_reported["TIME"], saved_time)

    def test_minute_of_day_conversion(self) -> None:
        """Chirp times convert properly to minutes of day (UOM 44)."""
        self.assertEqual(nodes._to_minute_of_day("00:00"), 0)
        self.assertEqual(nodes._to_minute_of_day("01:30"), 90)
        self.assertEqual(nodes._to_minute_of_day("23:59"), 1439)
        self.assertEqual(nodes._to_minute_of_day(120), 120)
        self.assertEqual(nodes._to_minute_of_day("invalid", 42), 42)

    def test_command_selector_extraction(self) -> None:
        """Extract selector integer from PG3 command payload dicts."""
        self.assertEqual(nodes.KiddeAlarmNode._extract_selector_value(1), 1)
        self.assertEqual(nodes.KiddeAlarmNode._extract_selector_value({"value": "3"}), 3)
        self.assertEqual(nodes.KiddeAlarmNode._extract_selector_value({"query": {"CMD": "2"}}), 2)
        # Default fallback is HUSH (4)
        self.assertEqual(nodes.KiddeAlarmNode._extract_selector_value(None), 4)


if __name__ == "__main__":
    unittest.main()
