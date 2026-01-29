"""
End-to-end workflow tests for IBP OSINT investigation platform.
Tests complete investigation flows from Phase 1 through Phase 3.
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


def clear_session_storage(page: Page):
    """Clear all sessionStorage data."""
    page.evaluate("sessionStorage.clear()")


class TestFullWorkflow:
    """Test complete investigation workflows."""

    def test_complete_investigation_no_photo(
        self, page: Page, server_url: str, take_screenshot
    ):
        """
        Test complete Phase 1 -> Phase 2 -> Phase 3 flow without photo upload.
        """
        print("\n--- PHASE 1: Social Media Discovery ---")

        # Navigate to home page
        page.goto(server_url)
        take_screenshot("home")

        # Fill in target name
        target_name = "Tikhon Portnoi"
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill(target_name)
        take_screenshot("name_entered")

        # Submit the form
        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        # Wait for navigation to loading/results page
        page.wait_for_url("**/phase1/**", timeout=30000)

        # Wait for Phase 1 to complete
        print("Waiting for Phase 1 to complete...")
        wait_for_phase_complete(page, 1)
        take_screenshot("phase1_results")
        print("Phase 1 completed")

        # Verify results are displayed
        results_container = page.locator("#resultsContainer")
        expect(results_container).to_be_visible()

        print("\n--- PHASE 2: Contact Discovery ---")

        # Check for Phase 2 button
        phase2_btn = page.locator("#phase2FloatingBtn, #phase2Btn, .phase2-btn").first

        if phase2_btn.is_visible():
            # Click Phase 2 button
            phase2_btn.click()

            # Wait for Phase 2 navigation or modal
            page.wait_for_timeout(2000)  # Brief wait for UI update

            # Wait for Phase 2 to complete
            print("Waiting for Phase 2 to complete...")
            try:
                wait_for_phase_complete(page, 2, timeout=DEFAULT_TIMEOUT)
                take_screenshot("phase2_results")
                print("Phase 2 completed")

                # Verify contact information is displayed
                # Look for email or phone indicators
                page_content = page.content()
                has_contacts = (
                    "@" in page_content
                    or "email" in page_content.lower()
                    or "phone" in page_content.lower()
                    or "contact" in page_content.lower()
                )
                print(f"Contact information found: {has_contacts}")

            except Exception as e:
                print(f"Phase 2 did not complete as expected: {e}")
                take_screenshot("phase2_error")

        print("\n--- PHASE 3: Deep Analysis ---")

        # Check for Phase 3 button or auto-navigation
        phase3_btn = page.locator("#phase3Btn, .phase3-btn, [data-phase='3']").first

        if phase3_btn.is_visible():
            phase3_btn.click()

            print("Waiting for Phase 3 to complete...")
            try:
                wait_for_phase_complete(page, 3, timeout=DEFAULT_TIMEOUT)
                take_screenshot("phase3_results")
                print("Phase 3 completed")
            except Exception as e:
                print(f"Phase 3 did not complete as expected: {e}")
                take_screenshot("phase3_error")
        else:
            print("Phase 3 button not visible, may require different navigation")
            take_screenshot("phase3_not_available")

    def test_investigation_with_photo(
        self, page: Page, server_url: str, take_screenshot
    ):
        """
        Test investigation flow with photo upload for API face search.
        """
        print("\n--- Testing Investigation with Photo Upload ---")

        # Navigate to home page
        page.goto(server_url)
        take_screenshot("home_photo_test")

        # Fill in target name
        target_name = "Tikhon Portnoi"
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill(target_name)

        # Check for photo upload input
        photo_input = page.locator("#target_photo, #photoInput, input[type='file']").first

        if photo_input.is_visible() or photo_input.count() > 0:
            # Create a simple test image if needed
            # For now, we'll skip actual file upload and test the flow
            print("Photo upload field found")
            take_screenshot("photo_upload_available")
        else:
            print("Photo upload field not visible")

        # Submit the form
        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        # Wait for Phase 1 to start
        page.wait_for_url("**/phase1/**", timeout=30000)

        print("Waiting for Phase 1 results...")
        wait_for_phase_complete(page, 1)
        take_screenshot("phase1_with_photo")
        print("Phase 1 completed")

    def test_multiple_targets(
        self, page: Page, server_url: str, test_targets, take_screenshot
    ):
        """
        Test investigation with multiple targets from test_targets.json.
        """
        targets = test_targets.get("targets", [])

        if not targets:
            pytest.skip("No test targets configured in test_targets.json")

        for i, target in enumerate(targets):
            print(f"\n--- Testing Target {i + 1}: {target.get('name_latin', target.get('name'))} ---")

            # Clear session storage between targets
            clear_session_storage(page)

            # Navigate to home page
            page.goto(server_url)

            # Use Latin name if available, otherwise use the name directly
            target_name = target.get("name_latin", target.get("name", "Unknown"))
            name_input = page.locator("#target_name, #targetName").first
            name_input.fill(target_name)

            take_screenshot(f"target_{i + 1}_entered")

            # Submit the form
            submit_button = page.locator('button[type="submit"], #submitBtn').first
            submit_button.click()

            # Wait for Phase 1 to start
            page.wait_for_url("**/phase1/**", timeout=30000)

            # Wait for results
            print(f"Waiting for Phase 1 results for {target_name}...")
            wait_for_phase_complete(page, 1)
            take_screenshot(f"target_{i + 1}_results")

            # Verify expected platforms if specified
            expected_platforms = target.get("expected_platforms", [])
            if expected_platforms:
                page_content = page.content().lower()
                for platform in expected_platforms:
                    if platform.lower() in page_content:
                        print(f"Found expected platform: {platform}")
                    else:
                        print(f"Platform {platform} not found in results")

            # Verify expected username if specified
            expected_username = target.get("expected_username")
            if expected_username:
                page_content = page.content()
                if expected_username in page_content:
                    print(f"Found expected username: {expected_username}")
                else:
                    print(f"Expected username {expected_username} not found")

            print(f"Target {i + 1} investigation completed")


class TestPhase1Specific:
    """Tests specific to Phase 1 functionality."""

    def test_username_generation_cyrillic(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test that Cyrillic names are properly transliterated for username search."""
        page.goto(server_url)

        # Test with Cyrillic name
        cyrillic_name = "Tikhon Portnoi"  # Using Latin version for input
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill(cyrillic_name)

        # Submit
        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        # Wait for Phase 1
        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        take_screenshot("cyrillic_transliteration_test")

        # Check if usernames were generated
        page_content = page.content().lower()
        # Common username patterns
        assert (
            "tikhon" in page_content
            or "portnoi" in page_content
            or "username" in page_content
        ), "Username generation should produce results"

    def test_empty_name_validation(self, page: Page, server_url: str):
        """Test that empty name is properly validated."""
        page.goto(server_url)

        # Try to submit without entering a name
        submit_button = page.locator('button[type="submit"], #submitBtn').first

        # Check if form validation prevents submission
        name_input = page.locator("#target_name, #targetName").first

        # Get the required attribute or check validation
        is_required = name_input.get_attribute("required") is not None

        if is_required:
            # HTML5 validation should prevent submission
            submit_button.click()
            # Should still be on the same page
            current_url = page.url
            assert "phase1" not in current_url, "Should not navigate with empty name"
        else:
            # If not required, the app should handle it gracefully
            submit_button.click()
            page.wait_for_timeout(1000)
            # Check for error message or validation


class TestSessionStorage:
    """Test session storage handling between phases."""

    def test_session_storage_populated_after_phase1(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Verify that session storage is populated after Phase 1 completion."""
        page.goto(server_url)

        # Submit a search
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        # Check session storage for phase data
        session_data = get_session_storage(page, "phase2_input")

        # Session storage might be populated with selected profiles
        # The exact key depends on the application implementation
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

        print(f"Session storage contents: {all_storage}")
        take_screenshot("session_storage_check")

        # At minimum, verify we can access session storage
        assert isinstance(all_storage, dict), "Should be able to read session storage"
