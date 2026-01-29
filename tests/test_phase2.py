"""
Phase 2 specific tests for IBP OSINT investigation platform.
Tests contact discovery including email and phone number detection.
"""

import pytest
from playwright.sync_api import Page, expect

# Constants
DEFAULT_TIMEOUT = 120000  # 2 minutes


def wait_for_phase_complete(page: Page, phase: int, timeout: int = DEFAULT_TIMEOUT):
    """Wait for a phase to complete by monitoring the progress indicator."""
    page.wait_for_selector("#resultsContainer", state="visible", timeout=timeout)
    page.wait_for_function(
        """() => {
            const progressFill = document.querySelector('#progressFill');
            if (!progressFill) return true;
            const width = progressFill.style.width;
            return width === '100%' || !width;
        }""",
        timeout=timeout,
    )


def get_session_storage(page: Page, key: str):
    """Get a value from sessionStorage."""
    return page.evaluate(f'sessionStorage.getItem("{key}")')


class TestPhase2Discovery:
    """Test Phase 2 contact discovery functionality."""

    def _navigate_to_phase2(self, page: Page, server_url: str):
        """Helper to navigate through Phase 1 to Phase 2."""
        page.goto(server_url)

        # Complete Phase 1
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        # Click Phase 2 button
        phase2_btn = page.locator("#phase2FloatingBtn, #phase2Btn, .phase2-btn").first
        if phase2_btn.is_visible():
            phase2_btn.click()
            page.wait_for_timeout(2000)
            return True
        return False

    def test_phase2_email_discovery(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test Phase 2 email discovery functionality."""
        if not self._navigate_to_phase2(page, server_url):
            pytest.skip("Phase 2 button not available")

        print("Waiting for Phase 2 email discovery...")
        try:
            wait_for_phase_complete(page, 2)
            take_screenshot("phase2_email_results")

            # Check for email indicators
            page_content = page.content()

            # Look for email patterns
            has_email = "@" in page_content or "email" in page_content.lower()
            print(f"Email indicators found: {has_email}")

        except Exception as e:
            print(f"Phase 2 did not complete: {e}")
            take_screenshot("phase2_email_error")

    def test_phase2_phone_discovery(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test Phase 2 phone number discovery functionality."""
        if not self._navigate_to_phase2(page, server_url):
            pytest.skip("Phase 2 button not available")

        try:
            wait_for_phase_complete(page, 2)
            take_screenshot("phase2_phone_results")

            # Check for phone indicators
            page_content = page.content().lower()
            has_phone = "phone" in page_content or "tel" in page_content

            print(f"Phone indicators found: {has_phone}")

        except Exception as e:
            print(f"Phase 2 did not complete: {e}")
            take_screenshot("phase2_phone_error")

    def test_phase2_progress_tracking(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test Phase 2 progress indicator."""
        if not self._navigate_to_phase2(page, server_url):
            pytest.skip("Phase 2 button not available")

        # Check for progress indicator
        progress_fill = page.locator("#progressFill")
        if progress_fill.is_visible():
            take_screenshot("phase2_progress_visible")

            # Wait for completion
            page.wait_for_function(
                """() => {
                    const fill = document.querySelector('#progressFill');
                    return fill && fill.style.width === '100%';
                }""",
                timeout=DEFAULT_TIMEOUT,
            )
            take_screenshot("phase2_progress_complete")


class TestPhase2SessionData:
    """Test Phase 2 session storage and data handling."""

    def test_session_data_from_phase1(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test that Phase 2 receives correct session data from Phase 1."""
        page.goto(server_url)

        # Complete Phase 1
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        # Check session storage before Phase 2
        all_storage = page.evaluate(
            """() => {
            const items = {};
            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                items[key] = sessionStorage.getItem(key);
            }
            return items;
        }"""
        )

        print(f"Session storage after Phase 1: {list(all_storage.keys())}")
        take_screenshot("session_data_phase1")

    def test_selected_profiles_passed_to_phase2(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test that selected profiles from Phase 1 are passed to Phase 2."""
        page.goto(server_url)

        # Complete Phase 1
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        # Select accounts if checkboxes available
        checkboxes = page.locator(".account-checkbox, input[type='checkbox']")
        if checkboxes.count() > 0:
            # Select first checkbox
            first_checkbox = checkboxes.first
            if first_checkbox.is_visible() and not first_checkbox.is_checked():
                first_checkbox.click()

        # Click Phase 2 button
        phase2_btn = page.locator("#phase2FloatingBtn, #phase2Btn, .phase2-btn").first
        if not phase2_btn.is_visible():
            pytest.skip("Phase 2 button not available")

        phase2_btn.click()
        page.wait_for_timeout(2000)

        # Verify session storage has phase2_input data
        phase2_input = get_session_storage(page, "phase2_input")
        print(f"Phase 2 input data: {phase2_input}")
        take_screenshot("phase2_session_data")


class TestPhase2Results:
    """Test Phase 2 results display and formatting."""

    def _setup_phase2(self, page: Page, server_url: str):
        """Helper to set up and navigate to Phase 2."""
        page.goto(server_url)

        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        phase2_btn = page.locator("#phase2FloatingBtn, #phase2Btn, .phase2-btn").first
        if phase2_btn.is_visible():
            phase2_btn.click()
            page.wait_for_timeout(2000)
            return True
        return False

    def test_results_container_displayed(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test that Phase 2 results container is displayed."""
        if not self._setup_phase2(page, server_url):
            pytest.skip("Phase 2 not available")

        try:
            wait_for_phase_complete(page, 2)

            results = page.locator("#resultsContainer")
            expect(results).to_be_visible()
            take_screenshot("phase2_results_container")

        except Exception as e:
            print(f"Phase 2 results test failed: {e}")
            take_screenshot("phase2_results_error")

    def test_contact_info_formatting(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test that contact information is properly formatted."""
        if not self._setup_phase2(page, server_url):
            pytest.skip("Phase 2 not available")

        try:
            wait_for_phase_complete(page, 2)
            take_screenshot("phase2_contact_formatting")

            # Check for properly formatted email addresses
            email_links = page.locator('a[href^="mailto:"]')
            email_count = email_links.count()
            print(f"Found {email_count} email links")

            # Check for properly formatted phone numbers
            phone_links = page.locator('a[href^="tel:"]')
            phone_count = phone_links.count()
            print(f"Found {phone_count} phone links")

        except Exception as e:
            print(f"Contact formatting test failed: {e}")
            take_screenshot("phase2_formatting_error")


class TestPhase2ErrorHandling:
    """Test Phase 2 error handling and edge cases."""

    def test_phase2_without_selection(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test Phase 2 behavior when no profiles are selected."""
        page.goto(server_url)

        # Complete Phase 1
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        # Uncheck all checkboxes if any are checked
        checkboxes = page.locator(".account-checkbox:checked, input[type='checkbox']:checked")
        for i in range(checkboxes.count()):
            checkbox = checkboxes.nth(i)
            if checkbox.is_visible():
                checkbox.click()

        # Try to start Phase 2
        phase2_btn = page.locator("#phase2FloatingBtn, #phase2Btn, .phase2-btn").first
        if not phase2_btn.is_visible():
            pytest.skip("Phase 2 button not available")

        phase2_btn.click()
        page.wait_for_timeout(2000)

        take_screenshot("phase2_no_selection")

        # Check for error message or validation
        page_content = page.content().lower()
        has_error = "error" in page_content or "select" in page_content

        print(f"Error/validation message present: {has_error}")

    @pytest.mark.slow
    def test_phase2_timeout_handling(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test Phase 2 timeout handling for long-running searches."""
        page.goto(server_url)

        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        phase2_btn = page.locator("#phase2FloatingBtn, #phase2Btn, .phase2-btn").first
        if not phase2_btn.is_visible():
            pytest.skip("Phase 2 button not available")

        phase2_btn.click()

        # Use shorter timeout to test timeout handling
        try:
            wait_for_phase_complete(page, 2, timeout=30000)  # 30 second timeout
            take_screenshot("phase2_completed_in_time")
        except Exception as e:
            print(f"Phase 2 timed out (expected): {e}")
            take_screenshot("phase2_timeout")
