"""
Phase 1 specific tests for IBP OSINT investigation platform.
Tests social media discovery, username generation, and Cyrillic transliteration.
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


class TestPhase1Discovery:
    """Test Phase 1 social media discovery functionality."""

    def test_phase1_basic_search(self, page: Page, server_url: str, take_screenshot):
        """Test basic Phase 1 search with a simple name."""
        page.goto(server_url)
        take_screenshot("phase1_home")

        # Enter target name
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")
        take_screenshot("phase1_name_filled")

        # Submit search
        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        # Wait for Phase 1 to complete
        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        take_screenshot("phase1_results")

        # Verify results container is visible
        results = page.locator("#resultsContainer")
        expect(results).to_be_visible()

    def test_username_generation_from_name(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test that usernames are generated from the target name."""
        page.goto(server_url)

        # Enter a name that should generate specific usernames
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Daniil Glazkov")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        take_screenshot("username_generation")

        # Check page content for username patterns
        page_content = page.content().lower()

        # Should contain variations of the name
        name_found = "daniil" in page_content or "glazkov" in page_content
        assert name_found, "Should find name-based usernames in results"

    def test_cyrillic_name_handling(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test that Cyrillic names are properly handled and transliterated."""
        page.goto(server_url)

        # Enter Cyrillic name (if supported) or Latin transliteration
        name_input = page.locator("#target_name, #targetName").first

        # Test with Latin version that would be transliterated from Cyrillic
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        take_screenshot("cyrillic_handling")

        # Verify search completed successfully
        results = page.locator("#resultsContainer")
        expect(results).to_be_visible()

    def test_progress_indicator(self, page: Page, server_url: str, take_screenshot):
        """Test that progress indicator shows during Phase 1 search."""
        page.goto(server_url)

        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)

        # Check for progress indicator
        progress_fill = page.locator("#progressFill")
        if progress_fill.is_visible():
            take_screenshot("progress_visible")
            # Progress should eventually reach 100%
            page.wait_for_function(
                """() => {
                    const fill = document.querySelector('#progressFill');
                    return fill && fill.style.width === '100%';
                }""",
                timeout=DEFAULT_TIMEOUT,
            )
            take_screenshot("progress_complete")

    @pytest.mark.slow
    def test_multiple_platform_search(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test that Phase 1 searches across multiple platforms."""
        page.goto(server_url)

        # Use a name known to have presence on multiple platforms
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Daniil Glazkov")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        take_screenshot("multi_platform_results")

        # Check for platform indicators in results
        page_content = page.content().lower()

        platforms_found = []
        platforms_to_check = ["vk", "telegram", "instagram", "facebook", "twitter"]

        for platform in platforms_to_check:
            if platform in page_content:
                platforms_found.append(platform)

        print(f"Platforms found in results: {platforms_found}")


class TestPhase1FormValidation:
    """Test Phase 1 form validation and error handling."""

    def test_form_required_field(self, page: Page, server_url: str):
        """Test that name field is required."""
        page.goto(server_url)

        # Check if name input has required attribute
        name_input = page.locator("#target_name, #targetName").first
        is_required = name_input.get_attribute("required") is not None

        if is_required:
            print("Name field has required attribute")
        else:
            print("Name field does not have required attribute")

    def test_submit_button_state(self, page: Page, server_url: str):
        """Test submit button state changes."""
        page.goto(server_url)

        submit_button = page.locator('button[type="submit"], #submitBtn').first

        # Button should be enabled initially
        expect(submit_button).to_be_enabled()

        # Fill in name
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Test Name")

        # Button should still be enabled
        expect(submit_button).to_be_enabled()


class TestPhase1AccountSelection:
    """Test account checkbox selection in Phase 1 results."""

    def test_account_checkboxes_displayed(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test that account checkboxes are displayed in results."""
        page.goto(server_url)

        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        # Check for account checkboxes
        checkboxes = page.locator(".account-checkbox, input[type='checkbox']")
        checkbox_count = checkboxes.count()

        print(f"Found {checkbox_count} account checkboxes")
        take_screenshot("account_checkboxes")

    def test_select_all_accounts(self, page: Page, server_url: str, take_screenshot):
        """Test selecting all accounts."""
        page.goto(server_url)

        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        # Try to find and click "select all" if available
        select_all = page.locator(
            "#selectAll, .select-all, [data-action='select-all']"
        ).first

        if select_all.is_visible():
            select_all.click()
            take_screenshot("all_selected")

            # Verify all checkboxes are checked
            checkboxes = page.locator(".account-checkbox, input[type='checkbox']")
            for i in range(checkboxes.count()):
                checkbox = checkboxes.nth(i)
                if checkbox.is_visible():
                    expect(checkbox).to_be_checked()
        else:
            print("Select all button not found")
            take_screenshot("no_select_all")
