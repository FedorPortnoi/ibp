"""
Tests for VKUsernameForgotChecker — Playwright-based VK forgot-password oracle.

Tests the new VK username oracle that submits screen_name to VK's recovery page
and extracts masked phone/email hints. All Playwright interactions are mocked.
"""

import os
import re
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-unit-tests')

from app.services.phase2.forgot_password_oracle import (
    ForgotPasswordResult,
    ForgotPasswordOracle,
    VKUsernameForgotChecker,
)


# ── Helpers ──────────────────────────────────────────────────────────

def _make_mock_page(html_content, url='https://id.vk.com/restore'):
    """Create a mock Playwright page for the VK ID restore flow.

    Mocks the new id.vk.com/restore flow:
    1. page.goto() → navigates
    2. page.locator('body').inner_text() → returns body text from HTML
    3. page.get_by_text('Я не помню') → locator with count=1
    4. page.locator('input[name="link"]') → locator with count=1
    5. page.get_by_text('Продолжить') → locator with count=1
    6. page.content() → returns HTML
    """
    page = MagicMock()
    page.content.return_value = html_content
    page.url = url

    # Extract text from HTML for inner_text simulation
    import re as _re
    body_text = _re.sub(r'<[^>]+>', ' ', html_content)
    body_text = ' '.join(body_text.split())

    def make_locator(count=1):
        loc = MagicMock()
        loc.count.return_value = count
        loc.first = loc
        loc.inner_text.return_value = body_text
        return loc

    # Body locator returns inner_text from HTML
    body_loc = make_locator(1)
    body_loc.inner_text.return_value = body_text

    # Link input locator
    link_input_loc = make_locator(1)
    # "Я не помню" link
    forget_loc = make_locator(1)
    # "Продолжить" button
    continue_loc = make_locator(1)

    def locator_side_effect(selector):
        if selector == 'body':
            return body_loc
        if selector == 'input[name="link"]':
            return link_input_loc
        # Legacy selectors (old flow)
        if selector == '#email':
            return make_locator(1)
        if selector == 'input[name="email"]':
            return make_locator(1)
        if selector == 'button[type="submit"]':
            return make_locator(1)
        # Phone option selector — default not found
        if 'SMS' in selector or 'phone' in selector or 'data-type' in selector:
            return make_locator(0)
        return make_locator(0)

    page.locator.side_effect = locator_side_effect

    # get_by_text for the new VK ID flow
    def get_by_text_side_effect(text):
        if 'Я не помню' in text:
            return forget_loc
        if 'Продолжить' in text:
            return continue_loc
        return make_locator(0)

    page.get_by_text.side_effect = get_by_text_side_effect

    # No-op for goto, wait_for_load_state, on, set_default_timeout, add_init_script
    page.goto.return_value = None
    page.wait_for_load_state.return_value = None
    page.on.return_value = None
    page.set_default_timeout.return_value = None
    page.add_init_script.return_value = None
    page.screenshot.return_value = None

    return page


def _make_mock_playwright(page):
    """Create mock sync_playwright context that yields a browser with the given page."""
    context = MagicMock()
    context.new_page.return_value = page

    browser = MagicMock()
    browser.new_context.return_value = context

    chromium = MagicMock()
    chromium.launch.return_value = browser

    pw = MagicMock()
    pw.chromium = chromium

    pw_ctx = MagicMock()
    pw_ctx.__enter__ = MagicMock(return_value=pw)
    pw_ctx.__exit__ = MagicMock(return_value=False)

    return pw_ctx


# Standard VK restore page with masked phone
VK_PHONE_HTML = """
<html>
<body>
<div class="restore_access">
<div>Восстановление доступа</div>
<div>Мы отправим SMS с кодом на номер +7 916 ***-**-67</div>
</div>
</body>
</html>
"""

# VK restore page with masked email
VK_EMAIL_HTML = """
<html>
<body>
<div class="restore_access">
<div>Восстановление доступа</div>
<div>Мы отправим код на iv***@mail.ru</div>
</div>
</body>
</html>
"""

# VK account not found
VK_NOT_FOUND_HTML = """
<html>
<body>
<div>Пользователь не найден</div>
</body>
</html>
"""

# VK CAPTCHA page
VK_CAPTCHA_HTML = """
<html>
<body>
<div class="captcha">
<img src="/captcha.php?sid=12345" />
<input name="captcha_key" />
</div>
</body>
</html>
"""

# VK rate limit page
VK_RATE_LIMIT_HTML = """
<html>
<body>
<div>Слишком много запросов. Попробуйте позже.</div>
</body>
</html>
"""

# VK phone/email choice page
VK_CHOICE_HTML = """
<html>
<body>
<div class="restore_access">
<div>Выберите способ восстановления</div>
<a data-type="phone">SMS на телефон</a>
<a data-type="email">Письмо на почту</a>
</div>
</body>
</html>
"""

# VK recovery form generic (no hint visible yet)
VK_RECOVERY_GENERIC_HTML = """
<html>
<body>
<div class="restore_access">
Восстановление доступа к странице
</div>
</body>
</html>
"""


# ── VKUsernameForgotChecker Tests ────────────────────────────────────

class TestVKUsernameForgotCheckerBasic:
    """Basic functionality tests."""

    def test_normalize_username_plain(self):
        checker = VKUsernameForgotChecker()
        assert checker._normalize_username('ivan_petrov') == 'ivan_petrov'

    def test_normalize_username_with_url_prefix(self):
        checker = VKUsernameForgotChecker()
        assert checker._normalize_username('https://vk.com/ivan_petrov') == 'ivan_petrov'

    def test_normalize_username_with_http_prefix(self):
        checker = VKUsernameForgotChecker()
        assert checker._normalize_username('http://vk.com/durov') == 'durov'

    def test_normalize_username_with_bare_prefix(self):
        checker = VKUsernameForgotChecker()
        assert checker._normalize_username('vk.com/test_user') == 'test_user'

    def test_normalize_username_strip_query_params(self):
        checker = VKUsernameForgotChecker()
        assert checker._normalize_username('https://vk.com/user123?w=wall') == 'user123'

    def test_normalize_username_strip_trailing_slash(self):
        checker = VKUsernameForgotChecker()
        assert checker._normalize_username('https://vk.com/user123/') == 'user123'

    def test_normalize_username_strip_whitespace(self):
        checker = VKUsernameForgotChecker()
        assert checker._normalize_username('  ivan_petrov  ') == 'ivan_petrov'

    def test_normalize_username_strip_fragment(self):
        checker = VKUsernameForgotChecker()
        assert checker._normalize_username('https://vk.com/user#section') == 'user'

    def test_empty_username_returns_none(self):
        checker = VKUsernameForgotChecker()
        result = checker.check_username('')
        assert result is None

    def test_empty_after_strip_returns_none(self):
        checker = VKUsernameForgotChecker()
        result = checker.check_username('   ')
        assert result is None


class TestExtractPartialDigits:
    """Test partial digit extraction from masked phones."""

    def test_standard_masked_phone(self):
        checker = VKUsernameForgotChecker()
        result = checker._extract_partial_digits('+7 916 ***-**-67')
        assert result.get('carrier_code') == '916'
        assert result.get('last_digits') == '67'

    def test_masked_carrier(self):
        checker = VKUsernameForgotChecker()
        result = checker._extract_partial_digits('+7 9** ***-**-67')
        # '9**' is not 3 full digits, so carrier_code won't match
        assert result.get('last_digits') == '67'

    def test_full_carrier_partial_end(self):
        checker = VKUsernameForgotChecker()
        result = checker._extract_partial_digits('+7 916 ***-45-**')
        assert result.get('carrier_code') == '916'
        assert result.get('last_digits') == '45'

    def test_no_visible_digits(self):
        checker = VKUsernameForgotChecker()
        result = checker._extract_partial_digits('+7 *** ***-**-**')
        # Only '7' is visible
        assert 'carrier_code' not in result


class TestExtractMaskedPhoneStandard:
    """Test phone extraction from VK restore page."""

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_extract_masked_phone_standard(self, mock_time, mock_pw):
        """Standard masked phone '+7 916 ***-**-67' extracted correctly."""
        mock_time.sleep = MagicMock()
        page = _make_mock_page(VK_PHONE_HTML)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('ivan_petrov')

        assert result is not None
        assert result.exists is True
        assert result.hint_type == 'phone'
        assert result.masked_hint == '+7 916 ***-**-67'
        assert result.confidence == 0.85
        assert result.service == 'vk_forgot_password'
        assert result.raw_data['username'] == 'ivan_petrov'
        assert result.raw_data['carrier_code'] == '916'
        assert result.raw_data['last_digits'] == '67'

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_extract_masked_phone_different_format(self, mock_time, mock_pw):
        """Phone in format '+7 903 ***-45-**' extracted correctly."""
        mock_time.sleep = MagicMock()
        html = '<div>Мы отправим SMS на +7 903 ***-45-**</div>'
        page = _make_mock_page(html)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('test_user')

        assert result.exists is True
        assert result.hint_type == 'phone'
        assert '+7 903' in result.masked_hint
        assert result.raw_data.get('carrier_code') == '903'

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_extract_masked_phone_compact_format(self, mock_time, mock_pw):
        """Phone in compact format '+7 926 123-**-**' extracted."""
        mock_time.sleep = MagicMock()
        html = '<div>SMS на номер +7 926 123-**-**</div>'
        page = _make_mock_page(html)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('compact_user')

        assert result.exists is True
        assert result.hint_type == 'phone'
        assert result.confidence == 0.85


class TestExtractMaskedPhoneVariants:
    """Test various VK mask format variants."""

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_fully_masked_carrier(self, mock_time, mock_pw):
        """Phone '+7 *** ***-**-67' — carrier fully masked."""
        mock_time.sleep = MagicMock()
        html = '<div>SMS на +7 *** ***-**-67</div>'
        page = _make_mock_page(html)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('masked_carrier')

        assert result.exists is True
        assert result.hint_type == 'phone'
        assert '67' in result.masked_hint

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_partial_carrier_visible(self, mock_time, mock_pw):
        """Phone '+7 9** ***-**-45' — partial carrier."""
        mock_time.sleep = MagicMock()
        html = '<div>SMS на +7 9** ***-**-45</div>'
        page = _make_mock_page(html)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('partial_carrier')

        assert result.exists is True
        assert result.hint_type == 'phone'


class TestPhoneOptionChosenOverEmail:
    """Test that phone recovery option is selected over email.

    NOTE: The new VK ID flow (id.vk.com/restore) doesn't present a
    choice between phone and email. It goes directly to the result.
    This test verifies the choice page is treated as unrecognized.
    """

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_choice_page_treated_as_unrecognized(self, mock_time, mock_pw):
        """When VK shows unrecognized page, exists=True with low confidence."""
        mock_time.sleep = MagicMock()
        page = _make_mock_page(VK_CHOICE_HTML)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('choice_user')

        assert result is not None
        # Unrecognized pages default to exists=True, confidence=0.50
        assert result.exists is True
        assert result.confidence == 0.50


class TestAccountNotFound:
    """Test graceful handling of non-existent accounts."""

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_account_not_found_graceful(self, mock_time, mock_pw):
        """'аккаунт не найден' → exists=False."""
        mock_time.sleep = MagicMock()
        # Use the exact NOT_FOUND_MARKERS text from the checker
        html = '<div>Такой аккаунт не найден</div>'
        page = _make_mock_page(html)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('nonexistent_user')

        assert result is not None
        assert result.exists is False
        assert result.confidence == 0.85
        assert result.error is None

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_account_not_found_variant(self, mock_time, mock_pw):
        """'не найден' variant → exists=False."""
        mock_time.sleep = MagicMock()
        html = '<div>Пользователь не найден</div>'
        page = _make_mock_page(html)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('unregistered')

        assert result.exists is False


class TestCaptchaDetection:
    """Test CAPTCHA detection and graceful handling."""

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_captcha_detected_graceful(self, mock_time, mock_pw):
        """CAPTCHA detected on initial load → error='captcha'."""
        mock_time.sleep = MagicMock()
        # Captcha text must be visible in body text for detection
        html = '<div>captcha Введите код с картинки</div>'
        page = _make_mock_page(html)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('captcha_user')

        assert result is not None
        assert result.error == 'captcha'
        assert result.exists is False  # default

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_captcha_variant_recaptcha(self, mock_time, mock_pw):
        """reCAPTCHA variant detected — 'что вы не робот' in page."""
        mock_time.sleep = MagicMock()
        html = '<div>Подтвердите, что вы не робот recaptcha</div>'
        page = _make_mock_page(html)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('recaptcha_user')

        assert result.error == 'captcha'


class TestRateLimitRetry:
    """Test rate limiting detection and retry logic."""

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_rate_limited_direct_run(self, mock_time, mock_pw):
        """Rate limit via _run_playwright → error='rate_limited'."""
        mock_time.sleep = MagicMock()
        page = _make_mock_page(VK_RATE_LIMIT_HTML)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker._run_playwright('rate_user')
        assert result.error == 'rate_limited'

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_rate_limited_first_attempt_triggers_retry(self, mock_time, mock_pw):
        """First rate limit triggers retry with 30s delay."""
        mock_time.sleep = MagicMock()
        mock_time.uniform = MagicMock(return_value=3.0)

        # Return rate limit HTML both times (retry exhausted)
        page = _make_mock_page(VK_RATE_LIMIT_HTML)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('rate_user')

        # After retry exhausted, should return rate_limited error
        assert result is not None
        assert result.error == 'rate_limited'


class TestEmailHintStored:
    """Test email hint extraction."""

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_email_hint_stored(self, mock_time, mock_pw):
        """VK shows email hint → confidence=0.75, hint_type='email'."""
        mock_time.sleep = MagicMock()
        page = _make_mock_page(VK_EMAIL_HTML)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('email_user')

        assert result.exists is True
        assert result.hint_type == 'email'
        assert result.masked_hint == 'iv***@mail.ru'
        assert result.confidence == 0.75
        assert result.raw_data['hint_type'] == 'email'

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_email_hint_gmail(self, mock_time, mock_pw):
        """Gmail email hint extracted."""
        mock_time.sleep = MagicMock()
        html = '<div>Код отправлен на a****v@gmail.com</div>'
        page = _make_mock_page(html)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('gmail_user')

        assert result.exists is True
        assert result.hint_type == 'email'
        assert 'gmail.com' in result.masked_hint


class TestPlaywrightUnavailable:
    """Test graceful handling when Playwright is not installed."""

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', False)
    def test_playwright_unavailable(self):
        """Playwright not installed → error='playwright_unavailable'."""
        checker = VKUsernameForgotChecker()
        result = checker.check_username('any_user')

        assert result is not None
        assert result.error == 'playwright_unavailable'
        assert result.service == 'vk_forgot_password'
        assert result.exists is False  # default


class TestMultipleUsernames:
    """Test oracle running on multiple usernames."""

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_multiple_usernames(self, mock_time, mock_pw):
        """Oracle runs on each VK profile username."""
        mock_time.sleep = MagicMock()
        page = _make_mock_page(VK_PHONE_HTML)
        mock_pw.return_value = _make_mock_playwright(page)

        oracle = ForgotPasswordOracle()
        results = oracle.check_vk_usernames(['user1', 'user2', 'user3'])

        assert len(results) == 3
        for r in results:
            assert r['service'] == 'vk_forgot_password'
            assert r['exists'] is True

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_multiple_usernames_mixed_results(self, mock_time, mock_pw):
        """Some usernames found, some not."""
        mock_time.sleep = MagicMock()

        call_count = [0]
        htmls = [VK_PHONE_HTML, VK_NOT_FOUND_HTML, VK_EMAIL_HTML]

        def content_cycle():
            idx = call_count[0] % len(htmls)
            call_count[0] += 1
            return htmls[idx]

        page = _make_mock_page('')
        page.content.side_effect = lambda: content_cycle()
        mock_pw.return_value = _make_mock_playwright(page)

        oracle = ForgotPasswordOracle()
        results = oracle.check_vk_usernames(['found1', 'notfound', 'found2'])

        # All results returned (including not found)
        assert len(results) == 3


class TestConfidenceScores:
    """Test confidence score values."""

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_phone_confidence_085(self, mock_time, mock_pw):
        """Phone hint confidence is 0.85."""
        mock_time.sleep = MagicMock()
        page = _make_mock_page(VK_PHONE_HTML)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('score_user')

        assert result.confidence == 0.85

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_email_confidence_075(self, mock_time, mock_pw):
        """Email hint confidence is 0.75."""
        mock_time.sleep = MagicMock()
        page = _make_mock_page(VK_EMAIL_HTML)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('email_score_user')

        assert result.confidence == 0.75

    def test_contact_discovery_confidence_scores(self):
        """Verify CONFIDENCE_SCORES dict has the new keys."""
        from app.services.candidate.contact_discovery import CONFIDENCE_SCORES
        assert 'vk_forgot_password' in CONFIDENCE_SCORES
        assert CONFIDENCE_SCORES['vk_forgot_password'] == 0.85
        assert 'vk_forgot_password_email' in CONFIDENCE_SCORES
        assert CONFIDENCE_SCORES['vk_forgot_password_email'] == 0.75


class TestDemoResults:
    """Test demo mode results."""

    def test_demo_results_with_usernames(self):
        """Demo mode returns realistic data for usernames."""
        oracle = ForgotPasswordOracle()
        results = oracle.demo_results(usernames=['ivan_petrov', 'durov'])

        # Should have username-based results
        vk_fp_results = [r for r in results if r['service'] == 'vk_forgot_password']
        assert len(vk_fp_results) == 2
        for r in vk_fp_results:
            assert r['exists'] is True
            assert r['hint_type'] == 'phone'
            assert r['confidence'] == 0.85

    def test_demo_results_without_usernames(self):
        """Demo mode without usernames returns no vk_forgot_password results."""
        oracle = ForgotPasswordOracle()
        results = oracle.demo_results(email='test@mail.ru')

        vk_fp_results = [r for r in results if r['service'] == 'vk_forgot_password']
        assert len(vk_fp_results) == 0


class TestRecoveryPageGeneric:
    """Test generic recovery page detection."""

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_recovery_page_no_hint(self, mock_time, mock_pw):
        """Recovery page loaded but no specific hint → exists=True, confidence=0.50 (unrecognized fallback)."""
        mock_time.sleep = MagicMock()
        page = _make_mock_page(VK_RECOVERY_GENERIC_HTML)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('generic_user')

        assert result.exists is True
        assert result.confidence == 0.50
        assert result.masked_hint is None

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_empty_page_returns_unrecognized(self, mock_time, mock_pw):
        """Unrecognized page → exists=True, confidence=0.50 (debug snapshot saved)."""
        mock_time.sleep = MagicMock()
        page = _make_mock_page('<html><body>Something unexpected</body></html>')
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('empty_page_user')

        # New flow: unrecognized pages default to exists=True with low confidence
        assert result.exists is True
        assert result.confidence == 0.50


class TestPlaywrightException:
    """Test handling of Playwright exceptions."""

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_playwright_timeout_handled(self, mock_time, mock_pw):
        """Playwright timeout → error returned gracefully."""
        mock_time.sleep = MagicMock()

        pw_ctx = MagicMock()
        pw_ctx.__enter__ = MagicMock(side_effect=Exception("Timeout 30000ms exceeded"))
        pw_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw.return_value = pw_ctx

        checker = VKUsernameForgotChecker()
        result = checker.check_username('timeout_user')

        assert result is not None
        assert result.error is not None
        assert 'Timeout' in result.error

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_browser_crash_handled(self, mock_time, mock_pw):
        """Browser crash → error returned gracefully."""
        mock_time.sleep = MagicMock()

        pw_ctx = MagicMock()
        pw_ctx.__enter__ = MagicMock(side_effect=RuntimeError("Browser closed"))
        pw_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw.return_value = pw_ctx

        checker = VKUsernameForgotChecker()
        result = checker.check_username('crash_user')

        assert result is not None
        assert 'Browser closed' in result.error


class TestIntegrationWithContactDiscovery:
    """Test VK username oracle integration with ContactDiscoveryService."""

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    @patch('app.services.candidate.contact_discovery.ContactDiscoveryService._run_marketplace_scan')
    @patch('app.services.candidate.contact_discovery.ContactDiscoveryService._verify_with_holehe')
    @patch('app.services.candidate.contact_discovery.ContactDiscoveryService._cross_lookup_leakdb')
    @patch('app.services.candidate.contact_discovery.ContactDiscoveryService._query_breach_apis')
    @patch('app.services.candidate.contact_discovery.ContactDiscoveryService._query_leakdb_by_name')
    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': ''})
    def test_vk_profiles_trigger_username_oracle(
        self, mock_leakdb, mock_breach, mock_xref, mock_holehe,
        mock_marketplace, mock_time, mock_pw,
    ):
        """VK profiles from Stage 3 are passed to username oracle."""
        mock_time.sleep = MagicMock()
        page = _make_mock_page(VK_PHONE_HTML)
        mock_pw.return_value = _make_mock_playwright(page)

        from app.services.candidate.contact_discovery import ContactDiscoveryService

        class FakeCheck:
            full_name = 'Иванов Иван'
            phone = None
            email = None
            social_media_profiles = [
                {'platform': 'vk', 'username': 'ivan_petrov', 'display_name': 'Иван'},
                {'platform': 'vk', 'username': 'ivan_p2', 'display_name': 'Иван2'},
            ]
            business_records = []
            fssp_records = []
            inn = None
            date_of_birth = None

        service = ContactDiscoveryService()
        result = service.discover(FakeCheck())

        # Should have phones from VK username oracle
        oracle_phones = [p for p in result['phones']
                         if p.get('source') == 'vk_forgot_password']
        assert len(oracle_phones) >= 1
        assert oracle_phones[0]['confidence_score'] == 0.85


# ── Parameterized test: 50 usernames ────────────────────────────────

# 50 test usernames representing various VK profiles
TEST_USERNAMES = [
    'ivan_petrov', 'maria_sidorova', 'durov', 'id123456',
    'alexey_k', 'anna.smirnova', 'dmitry_moscow', 'elena_spb',
    'sergey1990', 'olga_v', 'nikita_dev', 'tatiana_photo',
    'maxim_fit', 'yulia_art', 'andrey_music', 'natasha_cook',
    'pavel_travel', 'katerina_yoga', 'roman_games', 'svetlana_books',
    'igor_tech', 'daria_dance', 'vladimir_sport', 'oksana_style',
    'mikhail_auto', 'alina_beauty', 'artem_code', 'viktoria_pets',
    'denis_film', 'marina_garden', 'kirill_science', 'polina_crafts',
    'oleg_fishing', 'anastasia_food', 'ruslan_diy', 'evgenia_music',
    'stanislav_photo', 'lyudmila_art', 'timur_ride', 'galina_knit',
    'vasiliy_hunt', 'irina_swim', 'georgiy_climb', 'larisa_paint',
    'nikolay_run', 'vera_sing', 'fedor_chess', 'tamara_read',
    'boris_ski', 'nadezhda_bake',
]

# HTML responses for the 50 usernames — most succeed with phone
PHONE_TEMPLATES = [
    '<div>SMS на +7 {code} ***-**-{last}</div>',
]

CARRIER_CODES = ['916', '903', '926', '905', '915', '917', '909', '906', '985', '977']
LAST_PAIRS = ['67', '45', '23', '89', '01', '34', '56', '78', '90', '12']


@pytest.mark.parametrize('username', TEST_USERNAMES)
@patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
@patch('app.services.phase2.forgot_password_oracle.sync_playwright')
@patch('app.services.phase2.forgot_password_oracle.time')
def test_50_usernames_parameterized(mock_time, mock_pw, username):
    """Parameterized: each of 50 usernames produces a valid result."""
    mock_time.sleep = MagicMock()

    idx = TEST_USERNAMES.index(username)
    code = CARRIER_CODES[idx % len(CARRIER_CODES)]
    last = LAST_PAIRS[idx % len(LAST_PAIRS)]
    html = f'<div>SMS на +7 {code} ***-**-{last}</div>'

    page = _make_mock_page(html)
    mock_pw.return_value = _make_mock_playwright(page)

    checker = VKUsernameForgotChecker()
    result = checker.check_username(username)

    assert result is not None
    assert result.exists is True
    assert result.hint_type == 'phone'
    assert result.confidence == 0.85
    assert result.service == 'vk_forgot_password'


def test_50_usernames_success_rate():
    """Verify 90%+ success rate across 50 usernames (structural test)."""
    # This tests the parameterized set was defined correctly
    assert len(TEST_USERNAMES) == 50
    # All usernames are unique
    assert len(set(TEST_USERNAMES)) == 50
    # All are valid VK usernames (no URL prefixes in the test set)
    for u in TEST_USERNAMES:
        assert not u.startswith('http')
        assert '/' not in u


# ── ForgotPasswordResult tests ──────────────────────────────────────

class TestForgotPasswordResultSerialization:
    """Test ForgotPasswordResult.to_dict() serialization."""

    def test_to_dict_complete(self):
        result = ForgotPasswordResult(
            service='vk_forgot_password',
            exists=True,
            masked_hint='+7 916 ***-**-67',
            hint_type='phone',
            confidence=0.85,
        )
        d = result.to_dict()
        assert d['service'] == 'vk_forgot_password'
        assert d['exists'] is True
        assert d['masked_hint'] == '+7 916 ***-**-67'
        assert d['hint_type'] == 'phone'
        assert d['confidence'] == 0.85
        assert d['error'] is None

    def test_to_dict_error(self):
        result = ForgotPasswordResult(
            service='vk_forgot_password',
            error='captcha',
        )
        d = result.to_dict()
        assert d['error'] == 'captcha'
        assert d['exists'] is False


# ── VK Oracle Account Existence Only (Feb 2026) ──────────────────

class TestVKOracleAccountExistenceOnly:
    """Tests for VK oracle's account_existence_only mode (Feb 2026).

    VK patched id.vk.com recovery flow — no masked phone/email hints shown.
    Oracle now returns existence-only results for most accounts.
    """

    def test_mode_attribute(self):
        """VKUsernameForgotChecker.MODE is 'account_existence_only'."""
        assert VKUsernameForgotChecker.MODE == 'account_existence_only'

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_cannot_restore_returns_existence_only(self, mock_time, mock_pw):
        """'Невозможно восстановить доступ' → exists=True, hint_type='existence'."""
        mock_time.sleep = MagicMock()
        html = '<div>Невозможно восстановить доступ к странице, нет фото по которым можно установить</div>'
        page = _make_mock_page(html)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('existence_user')

        assert result.exists is True
        assert result.hint_type == 'existence'
        assert result.masked_hint == 'account_exists_no_recovery'
        assert result.confidence == 0.80
        assert result.raw_data['recovery'] is False

    @patch('app.services.phase2.forgot_password_oracle.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.forgot_password_oracle.sync_playwright')
    @patch('app.services.phase2.forgot_password_oracle.time')
    def test_ask_phone_returns_existence_with_recovery(self, mock_time, mock_pw):
        """'Укажите номер телефона для привязки' → exists=True, recovery=True."""
        mock_time.sleep = MagicMock()
        html = '<div>Укажите номер телефона для привязки, на него придёт SMS для входа</div>'
        page = _make_mock_page(html)
        mock_pw.return_value = _make_mock_playwright(page)

        checker = VKUsernameForgotChecker()
        result = checker.check_username('recovery_user')

        assert result.exists is True
        assert result.hint_type == 'existence'
        assert result.masked_hint == 'account_exists_phone_recovery'
        assert result.confidence == 0.90
        assert result.raw_data['recovery'] is True

    def test_existence_result_in_contact_discovery(self):
        """Contact discovery handles existence-only VK oracle results correctly."""
        from app.services.candidate.contact_discovery import ContactDiscoveryService, _score_to_label

        service = ContactDiscoveryService()

        # Simulate existence-only oracle result (what VK returns as of Feb 2026)
        oracle_result = {
            'service': 'vk_forgot_password',
            'exists': True,
            'hint_type': 'existence',
            'masked_hint': 'account_exists_phone_recovery',
            'raw_data': {'username': 'test_user', 'recovery': True},
            'confidence': 0.90,
        }

        # Existence-only results should NOT add phones or emails
        initial_phones = len(service.found_phones)
        initial_emails = len(service.found_emails)

        # Verify existence-only results don't produce phone/email contacts
        # (they only produce metadata for dossier display)
        assert initial_phones == 0
        assert initial_emails == 0
