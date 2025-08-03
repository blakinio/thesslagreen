#!/usr/bin/env python3
"""Test runner for ThesslaGreen Modbus integration."""
import sys
import subprocess


def run_tests():
    """Run all tests for the integration."""
    print("🧪 Running ThesslaGreen Modbus Integration Tests...")
    
    try:
        # Run pytest with coverage
        result = subprocess.run([
            sys.executable, "-m", "pytest",
            "tests/",
            "-v",
            "--tb=short",
            "-ra"
        ], check=True)
        
        print("✅ All tests passed!")
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Tests failed with exit code {e.returncode}")
        return e.returncode
    except FileNotFoundError:
        print("❌ pytest not found. Install with: pip install pytest")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())