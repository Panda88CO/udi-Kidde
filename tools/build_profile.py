#!/usr/bin/env python3
"""Generate PG3-compatible profile artifacts from JSON source files.

Reads:
  profile_source/nodedefs.json  -> profile/nodedef/nodedefs.xml
  profile_source/editors.json   -> profile/editor/editors.xml
  profile_source/nls_en_us.json -> profile/nls/en_us.txt

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
DEST = ROOT / "profile"


def _pretty_xml(element: ET.Element) -> str:
    raw = ET.tostring(element, encoding="unicode")
    dom = minidom.parseString(raw)
    lines = dom.toprettyxml(indent="   ", encoding=None).splitlines()
    # minidom adds an XML declaration; strip it so PG3 format matches.
    if lines and lines[0].startswith("<?xml"):
        lines = lines[1:]
    return "\n".join(line for line in lines if line.strip()) + "\n"


def build_nodedefs() -> None:
    src = json.loads((SRC / "nodedefs.json").read_text(encoding="utf-8"))
    root = ET.Element("nodeDefs")

    for nd in src["nodeDefs"]:
        node_el = ET.SubElement(root, "nodeDef", id=nd["id"], nls=nd["nls"])
        ET.SubElement(node_el, "editors")

        sts_el = ET.SubElement(node_el, "sts")
        for st in nd.get("sts", []):
            ET.SubElement(sts_el, "st", id=st["id"], editor=st["editor"])

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
                ET.SubElement(accepts_el, "cmd", id=cmd["id"])

    out = DEST / "nodedef" / "nodedefs.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_pretty_xml(root), encoding="utf-8")
    print(f"  wrote {out.relative_to(ROOT)}")


def build_editors() -> None:
    src = json.loads((SRC / "editors.json").read_text(encoding="utf-8"))
    root = ET.Element("editors")

    for ed in src["editors"]:
        ed_el = ET.SubElement(root, "editor", id=ed["id"])
        r = ed["range"]
        attrs = {"uom": str(r["uom"])}
        if "subset" in r:
            attrs["subset"] = r["subset"]
            attrs["nls"] = r["nls"]
        if "min" in r:
            attrs["min"] = str(r["min"])
            attrs["max"] = str(r["max"])
            attrs["step"] = str(r["step"])
        ET.SubElement(ed_el, "range", **attrs)

    out = DEST / "editor" / "editors.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_pretty_xml(root), encoding="utf-8")
    print(f"  wrote {out.relative_to(ROOT)}")


def build_nls() -> None:
    src = json.loads((SRC / "nls_en_us.json").read_text(encoding="utf-8"))
    lines: list[str] = []

    for value in src.get("nodes", {}).values():
        _ = value  # written below with keys
    for key, value in src.get("nodes", {}).items():
        lines.append(f"{key}={value}")

    lines.append("")
    for key, value in src.get("drivers", {}).items():
        lines.append(f"{key}={value}")

    lines.append("")
    for key, value in src.get("commands", {}).items():
        lines.append(f"{key}={value}")

    lines.append("")
    for key, value in src.get("enums", {}).items():
        lines.append(f"{key}={value}")

    out = DEST / "nls" / "en_us.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  wrote {out.relative_to(ROOT)}")


def main() -> None:
    print("Building profile artifacts from JSON sources...")
    build_nodedefs()
    build_editors()
    build_nls()
    print("Done.")


if __name__ == "__main__":
    sys.exit(main())
