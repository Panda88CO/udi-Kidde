#!/usr/bin/env python3
"""Generate PG3-compatible static profile artifacts from a single JSON source.

Reads:
    profile_source/profile.json -> profile_static/nodedef/nodedefs.xml
                                                             -> profile_static/editor/editors.xml
                                                             -> profile_static/nls/en_us.txt

Run from the repository root:
    python tools/build_profile.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.dom import minidom


ROOT = Path(__file__).resolve().parent.parent
SRC  = ROOT / "profile_source"
DEST = ROOT / "profile_static"
PROFILE_FILE = SRC / "profile.json"


def _pretty_xml(element: ET.Element) -> str:
    raw = ET.tostring(element, encoding="unicode")
    dom = minidom.parseString(raw)
    lines = dom.toprettyxml(indent="   ", encoding=None).splitlines()
    # minidom adds an XML declaration; strip it so PG3 format matches.
    if lines and lines[0].startswith("<?xml"):
        lines = lines[1:]
    return "\n".join(line for line in lines if line.strip()) + "\n"


def _load_profile() -> dict:
    return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))


def build_nodedefs(profile: dict) -> None:
    root = ET.Element("nodeDefs")

    for nd in profile.get("nodedefs", []):
        nls_id = f"nls{nd['id']}"
        node_el = ET.SubElement(root, "nodeDef", id=nd["id"], nls=nls_id)
        ET.SubElement(node_el, "editors")

        sts_el = ET.SubElement(node_el, "sts")
        for prop in nd.get("properties", []):
            ET.SubElement(sts_el, "st", id=prop["id"], editor=prop["editor"])

        cmds_el = ET.SubElement(node_el, "cmds")
        sends = nd.get("cmds", {}).get("sends", [])
        if sends:
            sends_el = ET.SubElement(cmds_el, "sends")
            for cmd in sends:
                ET.SubElement(sends_el, "cmd", id=cmd["id"])
        accepts = nd.get("cmds", {}).get("accepts", [])
        if accepts:
            accepts_el = ET.SubElement(cmds_el, "accepts")
            for cmd in accepts:
                cmd_el = ET.SubElement(accepts_el, "cmd", id=cmd["id"])
                for param in cmd.get("params", []):
                    attrs = {
                        "id": param["id"],
                        "editor": param["editor"],
                    }
                    if "uom" in param:
                        attrs["uom"] = str(param["uom"])
                    ET.SubElement(cmd_el, "p", **attrs)

    out = DEST / "nodedef" / "nodedefs.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_pretty_xml(root), encoding="utf-8")
    print(f"  wrote {out.relative_to(ROOT)}")


def build_editors(profile: dict) -> None:
    root = ET.Element("editors")

    for ed in profile.get("editors", []):
        ed_el = ET.SubElement(root, "editor", id=ed["id"])
        for r in ed.get("ranges", []):
            attrs = {"uom": str(r["uom"])}
            if "subset" in r:
                attrs["subset"] = r["subset"]
                if "names" in r:
                    attrs["nls"] = ed["id"]
            if "min" in r:
                attrs["min"] = str(r["min"])
            if "max" in r:
                attrs["max"] = str(r["max"])
            if "step" in r:
                attrs["step"] = str(r["step"])
            ET.SubElement(ed_el, "range", **attrs)

    out = DEST / "editor" / "editors.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_pretty_xml(root), encoding="utf-8")
    print(f"  wrote {out.relative_to(ROOT)}")


def build_nls(profile: dict) -> None:
    lines: list[str] = []

    for nd in profile.get("nodedefs", []):
        lines.append(f"ND-{nd['id']}-NAME={nd.get('name', nd['id'])}")
        if nd.get("icon"):
            lines.append(f"ND-{nd['id']}-ICON={nd['icon']}")

    lines.append("")
    for nd in profile.get("nodedefs", []):
        nls_id = f"nls{nd['id']}"
        for prop in nd.get("properties", []):
            key = f"ST-{nls_id}-{prop['id']}-NAME"
            value = prop.get("name", prop["id"])
            lines.append(f"{key}={value}")

    lines.append("")
    seen_cmd_labels: set[str] = set()
    for nd in profile.get("nodedefs", []):
        nls_id = f"nls{nd['id']}"
        for section in ("sends", "accepts"):
            for cmd in nd.get("cmds", {}).get(section, []):
                key = f"CMD-{nls_id}-{cmd['id']}-NAME"
                if key in seen_cmd_labels:
                    continue
                value = cmd.get("name", cmd["id"])
                lines.append(f"{key}={value}")
                seen_cmd_labels.add(key)
                for param in cmd.get("params", []):
                    param_name = param.get("name")
                    if not param_name:
                        continue
                    lines.append(f"CMDP-{nls_id}-{cmd['id']}-{param['id']}-NAME={param_name}")

    lines.append("")
    for ed in profile.get("editors", []):
        for r in ed.get("ranges", []):
            for value_key, value_name in r.get("names", {}).items():
                lines.append(f"{ed['id']}-{value_key}={value_name}")

    out = DEST / "nls" / "en_us.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  wrote {out.relative_to(ROOT)}")


def main() -> None:
    print("Building profile artifacts from JSON sources...")
    profile = _load_profile()
    build_nodedefs(profile)
    build_editors(profile)
    build_nls(profile)
    print("Done.")


if __name__ == "__main__":
    sys.exit(main())
