#!/usr/bin/env python3
"""
Test runner script for IBP automated tests.
Provides easy-to-use options for running tests with different configurations.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Run IBP automated tests with Playwright",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                    # Run all tests headless
  python run_tests.py --headed           # Run with visible browser
  python run_tests.py --fast             # Skip slow tests
  python run_tests.py -k test_phase1     # Run only phase1 tests
  python run_tests.py --failed           # Re-run only failed tests
        """,
    )

    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run tests with visible browser window",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run tests in headless mode (default)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip tests marked as slow",
    )
    parser.add_argument(
        "--failed",
        action="store_true",
        help="Re-run only previously failed tests",
    )
    parser.add_argument(
        "-k",
        "--keyword",
        type=str,
        help="Only run tests matching the given keyword expression",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Increase verbosity",
    )
    parser.add_argument(
        "--capture",
        choices=["no", "sys", "fd"],
        default="no",
        help="Capture mode for output (default: no)",
    )
    parser.add_argument(
        "test_path",
        nargs="?",
        default="tests/",
        help="Specific test file or directory to run",
    )

    args = parser.parse_args()

    # Get the project directory
    project_dir = Path(__file__).parent
    tests_dir = project_dir / "tests"
    screenshots_dir = tests_dir / "screenshots"

    # Create screenshots directory
    screenshots_dir.mkdir(exist_ok=True)
    print(f"Screenshots will be saved to: {screenshots_dir}")

    # Build pytest command (use sys.executable to ensure we use the right Python)
    pytest_args = [sys.executable, "-m", "pytest"]

    # Add test path
    pytest_args.append(str(project_dir / args.test_path))

    # Add verbosity
    if args.verbose:
        pytest_args.append("-vv")
    else:
        pytest_args.append("-v")

    # Add capture mode
    pytest_args.append(f"-s" if args.capture == "no" else f"--capture={args.capture}")

    # Skip slow tests if --fast
    if args.fast:
        pytest_args.append("-m")
        pytest_args.append("not slow")

    # Re-run failed tests
    if args.failed:
        pytest_args.append("--lf")

    # Keyword filter
    if args.keyword:
        pytest_args.append("-k")
        pytest_args.append(args.keyword)

    # Add short traceback
    pytest_args.append("--tb=short")

    # Set headed mode environment variable
    if args.headed:
        os.environ["PLAYWRIGHT_HEADED"] = "true"
        print("Running in HEADED mode (browser visible)")
    else:
        os.environ["PLAYWRIGHT_HEADED"] = "false"
        print("Running in HEADLESS mode")

    print(f"\nRunning: {' '.join(pytest_args)}\n")
    print("=" * 60)

    # Run pytest
    result = subprocess.run(pytest_args, cwd=project_dir)

    # Report results
    print("\n" + "=" * 60)
    if result.returncode == 0:
        print("ALL TESTS PASSED")
    else:
        print(f"TESTS FAILED (exit code: {result.returncode})")
        print(f"\nCheck screenshots in: {screenshots_dir}")

    # List any failure screenshots
    failure_screenshots = list(screenshots_dir.glob("FAILED_*.png"))
    if failure_screenshots:
        print("\nFailure screenshots:")
        for screenshot in failure_screenshots:
            print(f"  - {screenshot.name}")

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
