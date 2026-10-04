#!/usr/bin/env python3
"""Release Verification Test Runner for udi-Kidde.

Executes all release integrity, schema, controller, and alarm node tests.
Usage:
    python3 run_tests.py
    python3 run_tests.py -v
    python3 run_tests.py --failfast
"""

from __future__ import annotations

import argparse
import sys
import time
import unittest
from pathlib import Path

# Ensure root directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description="udi-Kidde Release Test Runner")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Run tests in verbose mode",
    )
    parser.add_argument(
        "-f", "--failfast",
        action="store_true",
        help="Stop execution on first failure or error",
    )
    parser.add_argument(
        "-k", "--pattern",
        type=str,
        default="test_*.py",
        help="Pattern to match test files (default: test_*.py)",
    )
    args = parser.parse_args()

    print("=" * 72)
    print("  udi-Kidde Release Verification Test Suite")
    print(f"  Python: {sys.version.split()[0]} | Platform: {sys.platform}")
    print(f"  Working Directory: {ROOT_DIR}")
    print("=" * 72)

    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=str(ROOT_DIR / "tests"),
        pattern=args.pattern,
        top_level_dir=str(ROOT_DIR),
    )

    verbosity = 2 if args.verbose else 1
    runner = unittest.TextTestRunner(
        verbosity=verbosity,
        failfast=args.failfast,
    )

    start_time = time.time()
    result = runner.run(suite)
    elapsed = time.time() - start_time

    print("\n" + "=" * 72)
    print(f"  Ran {result.testsRun} test(s) in {elapsed:.3f}s")
    print(f"  Passed: {result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)}")
    if result.failures:
        print(f"  Failures: {len(result.failures)}")
    if result.errors:
        print(f"  Errors: {len(result.errors)}")
    if result.skipped:
        print(f"  Skipped: {len(result.skipped)}")

    if result.wasSuccessful():
        print("  Status: 🚀 RELEASE READY (All tests passed)")
        print("=" * 72)
        return 0
    else:
        print("  Status: ❌ RELEASE BLOCKED (Failures or errors detected)")
        print("=" * 72)
        return 1


if __name__ == "__main__":
    sys.exit(main())

