"""Tests for dynamic PG3 profile schema, editor definitions, and UOM consistency."""

from __future__ import annotations

import unittest
try:
    from tests.conftest_mock import setup_mocks
except ImportError:
    from conftest_mock import setup_mocks

setup_mocks()

import nodes


class TestProfileSchema(unittest.TestCase):
    """Validate dynamic profile constraints, naming conventions, and UOM mappings."""

    def setUp(self) -> None:
        self.payload = nodes._dynamic_profile_payload()
        self.editors = self.payload["editors"]
        self.editor_map = {e["id"]: e for e in self.editors}
        self.nodedefs = self.payload["nodedefs"]
        self.nodedef_map = {n["id"]: n for n in self.nodedefs}

    def test_editor_id_naming_conventions(self) -> None:
        self.assertGreater(len(self.editors), 0)
        seen_ids = set()
        for editor in self.editors:
            eid = editor["id"]
            self.assertNotIn(eid, seen_ids, f"Duplicate editor ID: {eid}")
            seen_ids.add(eid)
            self.assertTrue(eid.isupper(), f"Editor ID '{eid}' must be all-uppercase")
            self.assertNotIn("_", eid, f"Editor ID '{eid}' must not contain underscores")

    def test_boolean_editor_definition(self) -> None:
        self.assertIn("BOOLEAN", self.editor_map, "Editor 'BOOLEAN' must exist")
        self.assertNotIn("bool", self.editor_map, "Old editor 'bool' must not exist")

        boolean_editor = self.editor_map["BOOLEAN"]
        ranges = boolean_editor.get("ranges", [])
        self.assertEqual(len(ranges), 1)
        r = ranges[0]
        self.assertEqual(r.get("uom"), "25", "BOOLEAN editor must use UOM 25")
        self.assertEqual(r.get("subset"), "0,1", "BOOLEAN editor must specify subset '0,1'")
        self.assertEqual(r.get("names"), {"0": "No", "1": "Yes"})

    def test_all_expected_editors_exist(self) -> None:
        expected_editors = {
            "BOOLEAN": "25",
            "CONNECT": "25",
            "COUNT": "56",
            "PPM": "54",
            "UNIXTIME": "151",
            "BATTERY": "25",
            "IAQ": "25",
            "MODELTYPE": "25",
            "MINUTEOFDAY": "44",
            "KIDDECOMMAND": "25",
        }
        for eid, expected_uom in expected_editors.items():
            with self.subTest(editor=eid):
                self.assertIn(eid, self.editor_map)
                ranges = self.editor_map[eid].get("ranges", [])
                self.assertEqual(ranges[0].get("uom"), expected_uom)

    def test_nodedef_id_naming_conventions(self) -> None:
        self.assertEqual(len(self.nodedefs), 9, "Expected SETUP + 8 KIDDEALARM variants")
        for nd in self.nodedefs:
            nid = nd["id"]
            self.assertTrue(nid.isupper(), f"Nodedef ID '{nid}' must be all-uppercase")
            self.assertNotIn("_", nid, f"Nodedef ID '{nid}' must not contain underscores")

        self.assertIn("SETUP", self.nodedef_map, "SETUP nodedef must exist")
        self.assertEqual(nodes.KiddeController.id, "SETUP")

        for bitmask in range(8):
            expected_id = f"KIDDEALARM{bitmask}"
            self.assertIn(expected_id, self.nodedef_map, f"Nodedef '{expected_id}' must exist")

    def test_sends_commands_have_no_name_attribute(self) -> None:
        """Release requirement: commands under 'sends' with DON/DOF must not have a 'name' attribute."""
        for nd in self.nodedefs:
            nid = nd["id"]
            sends = nd.get("cmds", {}).get("sends", [])
            for cmd in sends:
                cid = cmd.get("id")
                with self.subTest(nodedef=nid, command=cid):
                    self.assertIn(cid, ("DON", "DOF"), f"Unexpected command '{cid}' in sends")
                    self.assertNotIn(
                        "name",
                        cmd,
                        f"Nodedef '{nid}' sends command '{cid}' must not have a 'name' attribute",
                    )

    def test_property_editor_references(self) -> None:
        """Every property in every nodedef must reference a valid, existing editor ID."""
        for nd in self.nodedefs:
            nid = nd["id"]
            for prop in nd.get("properties", []):
                editor_ref = prop.get("editor")
                with self.subTest(nodedef=nid, property=prop.get("id")):
                    self.assertIn(
                        editor_ref,
                        self.editor_map,
                        f"Property '{prop.get('id')}' in '{nid}' references non-existent editor '{editor_ref}'",
                    )

    def test_command_parameter_editor_references(self) -> None:
        """Every command parameter in accepts must reference a valid editor ID."""
        for nd in self.nodedefs:
            nid = nd["id"]
            for cmd in nd.get("cmds", {}).get("accepts", []):
                for param in cmd.get("parameters", []):
                    editor_ref = param.get("editor")
                    with self.subTest(nodedef=nid, command=cmd.get("id"), param=param.get("id")):
                        self.assertIn(
                            editor_ref,
                            self.editor_map,
                            f"Command param '{param.get('id')}' in '{nid}' references non-existent editor '{editor_ref}'",
                        )

    def test_controller_driver_uom_consistency(self) -> None:
        """Drivers in KiddeController must have UOMs matching their editor's range UOM."""
        setup_nd = self.nodedef_map["SETUP"]
        prop_editors = {p["id"]: p["editor"] for p in setup_nd["properties"]}

        for driver_entry in nodes.KiddeController.drivers:
            did = driver_entry["driver"]
            driver_uom = driver_entry["uom"]
            editor_id = prop_editors[did]
            editor_uom = int(self.editor_map[editor_id]["ranges"][0]["uom"])
            with self.subTest(driver=did):
                self.assertEqual(
                    driver_uom,
                    editor_uom,
                    f"Controller driver '{did}' UOM ({driver_uom}) does not match editor '{editor_id}' UOM ({editor_uom})",
                )

    def test_alarm_nodes_driver_uom_consistency(self) -> None:
        """All 8 variants of KiddeAlarmNode must have driver UOMs matching their editor UOMs."""
        for smoke in (False, True):
            for co in (False, True):
                for iaq in (False, True):
                    alarm_node = nodes.KiddeAlarmNode(None, "SETUP", "d1", "Test", 1, 1, smoke, co, iaq)
                    nodedef_id = alarm_node.id
                    nodedef = self.nodedef_map[nodedef_id]
                    prop_editors = {p["id"]: p["editor"] for p in nodedef["properties"]}

                    for driver_entry in alarm_node.drivers:
                        did = driver_entry["driver"]
                        driver_uom = driver_entry["uom"]
                        editor_id = prop_editors[did]
                        editor_uom = int(self.editor_map[editor_id]["ranges"][0]["uom"])
                        with self.subTest(nodedef=nodedef_id, driver=did):
                            self.assertEqual(
                                driver_uom,
                                editor_uom,
                                f"Nodedef '{nodedef_id}' driver '{did}' UOM ({driver_uom}) != editor '{editor_id}' UOM ({editor_uom})",
                            )


if __name__ == "__main__":
    unittest.main()
