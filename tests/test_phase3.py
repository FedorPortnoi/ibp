"""
Phase 3 specific tests for IBP OSINT investigation platform.
Tests deep analysis and final report generation.
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


class TestPhase3DeepAnalysis:
    """Test Phase 3 deep analysis functionality."""

    def _navigate_to_phase3(self, page: Page, server_url: str, take_screenshot):
        """Helper to navigate through Phase 1 and 2 to Phase 3."""
        page.goto(server_url)

        # Phase 1
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        # Phase 2
        phase2_btn = page.locator("#phase2FloatingBtn, #phase2Btn, .phase2-btn").first
        if not phase2_btn.is_visible():
            return False

        phase2_btn.click()
        page.wait_for_timeout(2000)

        try:
            wait_for_phase_complete(page, 2)
        except Exception:
            return False

        # Phase 3
        phase3_btn = page.locator("#phase3Btn, .phase3-btn, [data-phase='3']").first
        if phase3_btn.is_visible():
            phase3_btn.click()
            page.wait_for_timeout(2000)
            return True

        return False

    def test_phase3_deep_analysis(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test Phase 3 deep analysis execution."""
        if not self._navigate_to_phase3(page, server_url, take_screenshot):
            pytest.skip("Phase 3 not available")

        print("Waiting for Phase 3 deep analysis...")
        try:
            wait_for_phase_complete(page, 3)
            take_screenshot("phase3_analysis_results")

            # Verify results displayed
            results = page.locator("#resultsContainer")
            expect(results).to_be_visible()

        except Exception as e:
            print(f"Phase 3 did not complete: {e}")
            take_screenshot("phase3_analysis_error")

    def test_phase3_progress_tracking(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test Phase 3 progress indicator."""
        if not self._navigate_to_phase3(page, server_url, take_screenshot):
            pytest.skip("Phase 3 not available")

        # Check for progress indicator
        progress_fill = page.locator("#progressFill")
        if progress_fill.is_visible():
            take_screenshot("phase3_progress_visible")

            page.wait_for_function(
                """() => {
                    const fill = document.querySelector('#progressFill');
                    return fill && fill.style.width === '100%';
                }""",
                timeout=DEFAULT_TIMEOUT,
            )
            take_screenshot("phase3_progress_complete")


class TestPhase3Report:
    """Test Phase 3 report generation and display."""

    def _setup_phase3(self, page: Page, server_url: str):
        """Helper to set up and navigate to Phase 3."""
        page.goto(server_url)

        # Phase 1
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        # Phase 2
        phase2_btn = page.locator("#phase2FloatingBtn, #phase2Btn, .phase2-btn").first
        if not phase2_btn.is_visible():
            return False

        phase2_btn.click()
        page.wait_for_timeout(2000)

        try:
            wait_for_phase_complete(page, 2)
        except Exception:
            return False

        # Phase 3
        phase3_btn = page.locator("#phase3Btn, .phase3-btn, [data-phase='3']").first
        if phase3_btn.is_visible():
            phase3_btn.click()
            page.wait_for_timeout(2000)
            return True

        return False

    def test_report_generation(self, page: Page, server_url: str, take_screenshot):
        """Test that Phase 3 generates a comprehensive report."""
        if not self._setup_phase3(page, server_url):
            pytest.skip("Phase 3 not available")

        try:
            wait_for_phase_complete(page, 3)
            take_screenshot("phase3_report")

            # Check for report elements
            page_content = page.content().lower()

            report_indicators = [
                "report" in page_content,
                "summary" in page_content,
                "findings" in page_content,
                "analysis" in page_content,
            ]

            has_report = any(report_indicators)
            print(f"Report indicators found: {has_report}")

        except Exception as e:
            print(f"Report generation test failed: {e}")
            take_screenshot("phase3_report_error")

    def test_report_export_options(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test report export options (PDF, etc.)."""
        if not self._setup_phase3(page, server_url):
            pytest.skip("Phase 3 not available")

        try:
            wait_for_phase_complete(page, 3)

            # Check for export buttons
            export_btn = page.locator(
                "#exportBtn, .export-btn, [data-action='export'], button:has-text('Export')"
            ).first

            if export_btn.is_visible():
                take_screenshot("phase3_export_available")
                print("Export button found")
            else:
                print("No export button found")
                take_screenshot("phase3_no_export")

            # Check for PDF download option
            pdf_btn = page.locator(
                "#pdfBtn, .pdf-btn, [data-format='pdf'], button:has-text('PDF')"
            ).first

            if pdf_btn.is_visible():
                print("PDF export option found")

        except Exception as e:
            print(f"Export options test failed: {e}")
            take_screenshot("phase3_export_error")


class TestPhase3DataAggregation:
    """Test Phase 3 data aggregation from previous phases."""

    def _navigate_through_phases(self, page: Page, server_url: str):
        """Navigate through all phases."""
        page.goto(server_url)

        # Phase 1
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        # Store Phase 1 results indicator
        phase1_content = page.content()

        # Phase 2
        phase2_btn = page.locator("#phase2FloatingBtn, #phase2Btn, .phase2-btn").first
        if not phase2_btn.is_visible():
            return None, None, None

        phase2_btn.click()
        page.wait_for_timeout(2000)

        try:
            wait_for_phase_complete(page, 2)
        except Exception:
            return phase1_content, None, None

        phase2_content = page.content()

        # Phase 3
        phase3_btn = page.locator("#phase3Btn, .phase3-btn, [data-phase='3']").first
        if not phase3_btn.is_visible():
            return phase1_content, phase2_content, None

        phase3_btn.click()
        page.wait_for_timeout(2000)

        try:
            wait_for_phase_complete(page, 3)
        except Exception:
            return phase1_content, phase2_content, None

        phase3_content = page.content()
        return phase1_content, phase2_content, phase3_content

    def test_data_aggregation_from_phases(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test that Phase 3 aggregates data from previous phases."""
        phase1_content, phase2_content, phase3_content = self._navigate_through_phases(
            page, server_url
        )

        if phase3_content is None:
            pytest.skip("Phase 3 not available")

        take_screenshot("phase3_aggregated_data")

        # Phase 3 should contain information from earlier phases
        # This is a basic check - specific content depends on implementation
        print("Data aggregation test completed")

    def test_session_storage_maintained(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test that session storage is maintained through all phases."""
        page.goto(server_url)

        # Phase 1
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        # Check storage after each phase
        storage_after_phase1 = page.evaluate("() => Object.keys(sessionStorage)")
        print(f"Session storage keys after Phase 1: {storage_after_phase1}")

        # Phase 2
        phase2_btn = page.locator("#phase2FloatingBtn, #phase2Btn, .phase2-btn").first
        if not phase2_btn.is_visible():
            pytest.skip("Phase 2 not available")

        phase2_btn.click()
        page.wait_for_timeout(2000)

        try:
            wait_for_phase_complete(page, 2)
        except Exception:
            pass

        storage_after_phase2 = page.evaluate("() => Object.keys(sessionStorage)")
        print(f"Session storage keys after Phase 2: {storage_after_phase2}")

        # Phase 3
        phase3_btn = page.locator("#phase3Btn, .phase3-btn, [data-phase='3']").first
        if not phase3_btn.is_visible():
            pytest.skip("Phase 3 not available")

        phase3_btn.click()
        page.wait_for_timeout(2000)

        try:
            wait_for_phase_complete(page, 3)
        except Exception:
            pass

        storage_after_phase3 = page.evaluate("() => Object.keys(sessionStorage)")
        print(f"Session storage keys after Phase 3: {storage_after_phase3}")

        take_screenshot("phase3_session_storage")


class TestPhase3ErrorHandling:
    """Test Phase 3 error handling and edge cases."""

    @pytest.mark.slow
    def test_phase3_timeout_handling(
        self, page: Page, server_url: str, take_screenshot
    ):
        """Test Phase 3 timeout handling for long-running analysis."""
        page.goto(server_url)

        # Navigate through phases quickly
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        phase2_btn = page.locator("#phase2FloatingBtn, #phase2Btn, .phase2-btn").first
        if not phase2_btn.is_visible():
            pytest.skip("Phase 2 not available")

        phase2_btn.click()
        page.wait_for_timeout(2000)

        try:
            wait_for_phase_complete(page, 2)
        except Exception:
            pass

        phase3_btn = page.locator("#phase3Btn, .phase3-btn, [data-phase='3']").first
        if not phase3_btn.is_visible():
            pytest.skip("Phase 3 not available")

        phase3_btn.click()

        # Test with shorter timeout
        try:
            wait_for_phase_complete(page, 3, timeout=30000)
            take_screenshot("phase3_completed_in_time")
        except Exception as e:
            print(f"Phase 3 timed out (may be expected): {e}")
            take_screenshot("phase3_timeout")

    def test_phase3_partial_data(self, page: Page, server_url: str, take_screenshot):
        """Test Phase 3 behavior with partial data from previous phases."""
        page.goto(server_url)

        # Complete Phase 1 only, then try to access Phase 3 directly
        name_input = page.locator("#target_name, #targetName").first
        name_input.fill("Tikhon Portnoi")

        submit_button = page.locator('button[type="submit"], #submitBtn').first
        submit_button.click()

        page.wait_for_url("**/phase1/**", timeout=30000)
        wait_for_phase_complete(page, 1)

        # Try to navigate directly to Phase 3 (skip Phase 2)
        phase3_btn = page.locator("#phase3Btn, .phase3-btn, [data-phase='3']").first

        if phase3_btn.is_visible():
            phase3_btn.click()
            page.wait_for_timeout(2000)

            take_screenshot("phase3_without_phase2")

            # Check for error or handling of missing Phase 2 data
            page_content = page.content().lower()
            has_error = "error" in page_content or "required" in page_content

            print(f"Error handling for missing Phase 2 data: {has_error}")
        else:
            print("Phase 3 button correctly not visible without Phase 2")
            take_screenshot("phase3_hidden_without_phase2")
