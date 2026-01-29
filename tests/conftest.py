"""
Pytest configuration and fixtures for IBP automated testing.
"""

import json
import os
import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, Page, Browser

# Configuration
SERVER_URL = "http://127.0.0.1:5000"
SERVER_START_COMMAND = ["python", "run.py"]
SERVER_STARTUP_WAIT = 3  # seconds
DEFAULT_TIMEOUT = 120000  # 2 minutes for async operations

# Directories
TESTS_DIR = Path(__file__).parent
PROJECT_DIR = TESTS_DIR.parent
SCREENSHOTS_DIR = TESTS_DIR / "screenshots"
TEST_DATA_DIR = TESTS_DIR / "test_data"


@pytest.fixture(scope="session")
def screenshots_dir():
    """Ensure screenshots directory exists."""
    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    return SCREENSHOTS_DIR


@pytest.fixture(scope="session")
def flask_server():
    """Start the Flask server for the test session."""
    # Start the server
    process = subprocess.Popen(
        SERVER_START_COMMAND,
        cwd=PROJECT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    time.sleep(SERVER_STARTUP_WAIT)

    # Check if server started successfully
    if process.poll() is not None:
        stdout, stderr = process.communicate()
        raise RuntimeError(
            f"Flask server failed to start:\n"
            f"stdout: {stdout.decode()}\n"
            f"stderr: {stderr.decode()}"
        )

    yield process

    # Teardown: terminate the server
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


@pytest.fixture(scope="session")
def playwright_instance():
    """Create a Playwright instance for the session."""
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright_instance, flask_server):
    """Create a browser instance for the session."""
    # Check if running in headed mode
    headed = os.environ.get("PLAYWRIGHT_HEADED", "false").lower() == "true"

    browser = playwright_instance.chromium.launch(
        headless=not headed,
        slow_mo=100 if headed else 0,  # Slow down for visibility in headed mode
    )

    yield browser

    browser.close()


@pytest.fixture(scope="function")
def context(browser):
    """Create a new browser context for each test."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )

    yield context

    context.close()


@pytest.fixture(scope="function")
def page(context, screenshots_dir) -> Page:
    """Create a fresh page for each test."""
    page = context.new_page()
    page.set_default_timeout(DEFAULT_TIMEOUT)

    yield page

    page.close()


@pytest.fixture(scope="session")
def test_targets():
    """Load test targets from JSON file."""
    targets_file = TEST_DATA_DIR / "test_targets.json"

    if not targets_file.exists():
        return {"targets": []}

    with open(targets_file, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def take_screenshot(page, screenshots_dir, request):
    """Factory fixture to take screenshots with sequential naming."""
    screenshot_counter = [0]  # Use list for mutable closure

    def _take_screenshot(name: str = None) -> Path:
        screenshot_counter[0] += 1
        if name:
            filename = f"{screenshot_counter[0]:02d}_{name}.png"
        else:
            filename = f"{screenshot_counter[0]:02d}_{request.node.name}.png"

        filepath = screenshots_dir / filename
        page.screenshot(path=str(filepath), full_page=True)
        print(f"Screenshot saved: {filepath}")
        return filepath

    return _take_screenshot


@pytest.fixture
def server_url():
    """Return the server URL."""
    return SERVER_URL


# Pytest hooks for automatic screenshot on failure
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Take screenshot on test failure."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        # Try to get the page fixture
        page = item.funcargs.get("page")
        if page:
            # Ensure screenshots directory exists
            SCREENSHOTS_DIR.mkdir(exist_ok=True)

            screenshot_path = SCREENSHOTS_DIR / f"FAILED_{item.name}.png"
            try:
                page.screenshot(path=str(screenshot_path), full_page=True)
                print(f"\nFailure screenshot saved: {screenshot_path}")
            except Exception as e:
                print(f"\nFailed to take screenshot: {e}")


# Helper functions that can be used in tests
def wait_for_phase_complete(page: Page, phase: int, timeout: int = DEFAULT_TIMEOUT):
    """
    Wait for a phase to complete by monitoring the progress indicator.

    Args:
        page: Playwright page object
        phase: Phase number (1, 2, or 3)
        timeout: Maximum wait time in milliseconds
    """
    # Wait for results container to be visible
    page.wait_for_selector("#resultsContainer", state="visible", timeout=timeout)

    # Wait for progress to complete (100%)
    page.wait_for_function(
        """() => {
            const progressFill = document.querySelector('#progressFill');
            if (!progressFill) return true;  // No progress bar means complete
            const width = progressFill.style.width;
            return width === '100%' || !width;
        }""",
        timeout=timeout,
    )


def get_session_storage(page: Page, key: str):
    """Get a value from sessionStorage."""
    return page.evaluate(f'sessionStorage.getItem("{key}")')


def set_session_storage(page: Page, key: str, value: str):
    """Set a value in sessionStorage."""
    page.evaluate(f'sessionStorage.setItem("{key}", {json.dumps(value)})')


def clear_session_storage(page: Page):
    """Clear all sessionStorage data."""
    page.evaluate("sessionStorage.clear()")
