#!/usr/bin/env python3
"""
Test runner script with coverage reporting
"""
import sys
import subprocess
from pathlib import Path

# Ensure we're using the venv
venv_python = Path(__file__).parent / "venv" / "bin" / "python"
if not venv_python.exists():
    venv_python = Path(sys.executable)

def run_tests():
    """Run tests with coverage"""
    cmd = [
        str(venv_python), "-m", "pytest",
        "tests/",
        "-v",
        "--cov=backend",
        "--cov-report=term-missing",
        "--cov-report=html",
        "--cov-config=.coveragerc",
        "--cov-fail-under=80"
    ]
    
    print("Running tests with coverage...")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)
    
    result = subprocess.run(cmd)
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_tests())

