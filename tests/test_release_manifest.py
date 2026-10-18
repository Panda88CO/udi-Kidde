"""Release manifest and package integrity tests for udi-Kidde."""

from __future__ import annotations

import json
import py_compile
import re
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestReleaseManifest(unittest.TestCase):
    """Verify package metadata, manifests, versioning, and scripts."""

    def test_server_json_structure(self) -> None:
        server_json = ROOT_DIR / "server.json"
        self.assertTrue(server_json.exists(), "server.json must exist in the root directory")

        data = json.loads(server_json.read_text(encoding="utf-8"))
        self.assertIn("name", data)
        self.assertIn("executable", data)
        self.assertIn("description", data)

        executable_path = ROOT_DIR / data["executable"]
        self.assertTrue(executable_path.exists(), f"Executable '{data['executable']}' must exist")

        self.assertIsInstance(data.get("shortPoll"), int)
        self.assertIsInstance(data.get("longPoll"), int)
        self.assertGreater(data["shortPoll"], 0)
        self.assertGreater(data["longPoll"], 0)

    def test_install_script(self) -> None:
        install_sh = ROOT_DIR / "install.sh"
        self.assertTrue(install_sh.exists(), "install.sh must exist in the root directory")
        content = install_sh.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("#!"), "install.sh must have a shebang")
        self.assertIn("requirements.txt", content, "install.sh must reference requirements.txt")

    def test_requirements_file(self) -> None:
        req_file = ROOT_DIR / "requirements.txt"
        self.assertTrue(req_file.exists(), "requirements.txt must exist in root directory")
        reqs = req_file.read_text(encoding="utf-8").lower()
        self.assertIn("udi_interface", reqs, "requirements.txt must require udi_interface")
        self.assertIn("kidde-homesafe", reqs, "requirements.txt must require kidde-homesafe")

    def test_version_in_entrypoint(self) -> None:
        entrypoint = ROOT_DIR / "udi_kidde.py"
        self.assertTrue(entrypoint.exists(), "udi_kidde.py must exist")
        code = entrypoint.read_text(encoding="utf-8")

        # Must have polyglot.start({"version": "x.y.z", ...})
        match = re.search(r'"version"\s*:\s*"(\d+\.\d+\.\d+)"', code)
        self.assertIsNotNone(match, "udi_kidde.py must specify a valid semantic version string")
        version_str = match.group(1)
        major, minor, patch = map(int, version_str.split("."))
        self.assertGreaterEqual((major, minor, patch), (0, 1, 6), "Version must be at least 0.1.6")

    def test_python_syntax_of_all_files(self) -> None:
        py_files = list(ROOT_DIR.glob("*.py")) + list((ROOT_DIR / "tools").glob("*.py"))
        self.assertGreater(len(py_files), 0, "Expected at least one Python file")
        for py_file in py_files:
            with self.subTest(file=py_file.name):
                # py_compile.compile raises PyCompileError on syntax failure
                py_compile.compile(str(py_file), doraise=True)


if __name__ == "__main__":
    unittest.main()

