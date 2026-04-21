#!/usr/bin/env python3
"""Test runner for ThesslaGreen Modbus integration."""

from __future__ import annotations

import argparse
import subprocess  # nosec B404
import sys

STABLE_TESTS = [
    "tests/test_config_flow.py",
    "tests/test_config_flow_helpers.py",
    "tests/test_services.py",
    "tests/test_scanner_register_cache_invalidation.py",
    "tests/test_init_helpers.py",
]


def _check_test_dependencies() -> int:
    """Ensure required test dependencies are installed."""
    try:
        __import__("homeassistant")
    except ModuleNotFoundError:
        print("❌ Missing dependency: homeassistant")
        print("   Install dev dependencies, e.g.: pip install -r requirements-dev.txt")
        return 1
    return 0


def _run_pytest_targets(test_targets: list[str], label: str) -> int:
    """Run pytest against provided targets and return process exit code."""
    print(f"🧪 Running ThesslaGreen Modbus Integration Tests ({label})...")
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *test_targets,
        "-v",
        "--tb=short",
        "-ra",
    ]

    deps_code = _check_test_dependencies()
    if deps_code != 0:
        return deps_code

    try:
        subprocess.run(cmd, check=True)  # nosec B603
        print("✅ All tests passed!")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Tests failed with exit code {e.returncode}")
        return e.returncode
    except FileNotFoundError:
        print("❌ pytest not found. Install with: pip install pytest")
        return 1


def run_tests(suite: str) -> int:
    """Run integration tests for the selected suite."""
    if suite == "stable":
        return _run_pytest_targets(STABLE_TESTS, "stable")
    if suite == "full":
        return _run_pytest_targets(["tests/"], "full")
    # gate mode: stable first, then full only if stable passes
    stable_code = _run_pytest_targets(STABLE_TESTS, "gate:stable")
    if stable_code != 0:
        return stable_code
    return _run_pytest_targets(["tests/"], "gate:full")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ThesslaGreen test suites")
    parser.add_argument(
        "--suite",
        choices=["stable", "full", "gate"],
        default="stable",
        help="stable: fast compatibility subset, full: entire tree, gate: stable then full",
    )
    args = parser.parse_args()
    sys.exit(run_tests(args.suite))
