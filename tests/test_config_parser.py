"""Tests for configuration parser."""

from __future__ import annotations

import unittest
from config_parser import KiddeConfig, _normalize_temp_unit, build_config


class TestConfigParser(unittest.TestCase):
    """Verify Kidde configuration parameter parsing and unit normalization."""

    def test_normalize_temp_unit(self) -> None:
        self.assertEqual(_normalize_temp_unit("F"), "F")
        self.assertEqual(_normalize_temp_unit("f"), "F")
        self.assertEqual(_normalize_temp_unit("fahrenheit"), "F")
        self.assertEqual(_normalize_temp_unit("FAHRENHEIT"), "F")
        self.assertEqual(_normalize_temp_unit("C"), "C")
        self.assertEqual(_normalize_temp_unit("c"), "C")
        self.assertEqual(_normalize_temp_unit("celsius"), "C")
        self.assertEqual(_normalize_temp_unit("CELSIUS"), "C")
        # Defaults to F on invalid/empty
        self.assertEqual(_normalize_temp_unit(""), "F")
        self.assertEqual(_normalize_temp_unit(None), "F")
        self.assertEqual(_normalize_temp_unit("XYZ"), "F")

    def test_build_config(self) -> None:
        # Empty parameters
        cfg1 = build_config({})
        self.assertEqual(cfg1.email, "")
        self.assertEqual(cfg1.password, "")
        self.assertEqual(cfg1.temp_unit, "F")

        # Full parameters
        cfg2 = build_config({
            "EMAIL": "  test@domain.com  ",
            "PASSWORD": "mysecretpassword",
            "TEMP_UNIT": "C",
        })
        self.assertEqual(cfg2.email, "test@domain.com")
        self.assertEqual(cfg2.password, "mysecretpassword")
        self.assertEqual(cfg2.temp_unit, "C")


if __name__ == "__main__":
    unittest.main()

