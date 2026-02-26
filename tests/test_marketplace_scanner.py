"""
Tests for MarketplaceScanner — Russian classifieds platform scanner.

Tests the 6 marketplace scanners (Avito, Youla, CIAN, Auto.ru, Yandex, VK Market),
the MarketplaceOracle orchestrator, demo mode, and the Playwright-based
Avito phone extraction (clicking "Показать номер").
"""

import os
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-unit-tests')

from app.services.phase2.marketplace_scanner import (
    AvitoScanner, YoulaScanner, CianScanner, AutoRuScanner,
    YandexSearchScanner, VKMarketScanner, MarketplaceOracle,
    MarketplaceListing, ScannerResult, PHONE_PATTERN, EMAIL_PATTERN,
)


# ── Unit Tests: Data Classes ─────────────────────────────────────

class TestMarketplaceListing:
    def test_default_fields(self):
        listing = MarketplaceListing()
        assert listing.title == ""
        assert listing.phone == ""
        assert listing.city == ""
        assert listing.category == ""
        assert listing.source == ""

    def test_custom_fields(self):
        listing = MarketplaceListing(
            title="iPhone 13", phone="+79161234567", city="Москва",
            source="avito", category="Телефоны",
        )
        assert listing.title == "iPhone 13"
        assert listing.phone == "+79161234567"
        assert listing.city == "Москва"
        assert listing.category == "Телефоны"


class TestScannerResult:
    def test_to_dict(self):
        result = ScannerResult(source="avito")
        result.phones_found = ["+79161234567"]
        result.emails_found = ["test@mail.ru"]
        result.listings.append(MarketplaceListing(
            title="Test", city="Москва", category="Авто",
        ))
        d = result.to_dict()
        assert d["source"] == "avito"
        assert d["phones_found"] == ["+79161234567"]
        assert d["emails_found"] == ["test@mail.ru"]
        assert d["listings"][0]["category"] == "Авто"

    def test_empty_result(self):
        result = ScannerResult(source="youla")
        d = result.to_dict()
        assert d["listings"] == []
        assert d["phones_found"] == []


# ── Unit Tests: Phone/Email Extraction ────────────────────────────

class TestPhoneExtraction:
    def test_russian_phone_plus7(self):
        scanner = AvitoScanner()
        phones = scanner._extract_phones("Звоните: +7 (916) 123-45-67")
        assert len(phones) >= 1

    def test_russian_phone_8(self):
        scanner = AvitoScanner()
        phones = scanner._extract_phones("Тел: 8-903-111-22-33")
        assert len(phones) >= 1

    def test_no_phone(self):
        scanner = AvitoScanner()
        phones = scanner._extract_phones("Нет телефона в тексте")
        assert phones == []


class TestEmailExtraction:
    def test_extract_email(self):
        scanner = AvitoScanner()
        emails = scanner._extract_emails("Пишите: seller@mail.ru")
        assert "seller@mail.ru" in emails

    def test_filter_service_emails(self):
        scanner = AvitoScanner()
        emails = scanner._extract_emails("Email: support@avito.ru test@test.com")
        assert "support@avito.ru" not in emails
        assert "test@test.com" not in emails

    def test_no_email(self):
        scanner = AvitoScanner()
        emails = scanner._extract_emails("Нет email")
        assert emails == []


# ── Unit Tests: Individual Scanners ───────────────────────────────

class TestAvitoScanner:
    @patch.object(AvitoScanner, '_safe_get')
    def test_search_by_name_http(self, mock_get):
        """HTTP-only search when Playwright not available."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = """
        <div data-marker="item">
            <span itemprop="name">iPhone 13</span>
            <a itemprop="url" href="/item/123">Link</a>
            <div>+7 (916) 123-45-67</div>
        </div>
        """
        mock_get.return_value = mock_resp

        scanner = AvitoScanner()
        with patch('app.services.phase2.marketplace_scanner.PLAYWRIGHT_AVAILABLE', False):
            result = scanner.search_by_name("Иванов Иван")

        assert result.source == "avito"
        assert len(result.listings) >= 1

    @patch.object(AvitoScanner, '_safe_get')
    def test_search_by_phone(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<div data-marker="item"><span itemprop="name">Test</span></div>'
        mock_get.return_value = mock_resp

        scanner = AvitoScanner()
        with patch('app.services.phase2.marketplace_scanner.PLAYWRIGHT_AVAILABLE', False):
            result = scanner.search_by_phone("+79161234567")

        assert result.source == "avito"

    @patch.object(AvitoScanner, '_safe_get')
    def test_http_fallback_on_failure(self, mock_get):
        """When HTTP request fails, result has error."""
        mock_get.return_value = None

        scanner = AvitoScanner()
        with patch('app.services.phase2.marketplace_scanner.PLAYWRIGHT_AVAILABLE', False):
            result = scanner.search_by_name("Test")

        assert len(result.errors) >= 1


class TestYoulaScanner:
    @patch.object(YoulaScanner, '_safe_get')
    def test_search_by_name(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<li class="product-item"><h3>Test Item</h3></li>'
        mock_get.return_value = mock_resp

        result = YoulaScanner().search_by_name("Петров")
        assert result.source == "youla"


class TestCianScanner:
    @patch.object(CianScanner, '_safe_get')
    def test_search_by_name(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<div data-name="CardComponent"><a class="title">Квартира</a></div>'
        mock_get.return_value = mock_resp

        result = CianScanner().search_by_name("Сидоров")
        assert result.source == "cian"


class TestAutoRuScanner:
    @patch.object(AutoRuScanner, '_safe_get')
    def test_search_by_name(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<div class="ListingItem"><a class="Link">Toyota</a></div>'
        mock_get.return_value = mock_resp

        result = AutoRuScanner().search_by_name("Козлов")
        assert result.source == "auto_ru"


class TestVKMarketScanner:
    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': ''})
    def test_not_available_without_token(self):
        scanner = VKMarketScanner(vk_token='')
        assert not scanner.is_available()

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'test_token'})
    def test_available_with_token(self):
        scanner = VKMarketScanner(vk_token='test_token')
        assert scanner.is_available()


# ── Tests: MarketplaceOracle Orchestrator ─────────────────────────

class TestMarketplaceOracle:
    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': ''})
    def test_demo_mode_by_name(self):
        """Demo mode returns realistic results when VK_SERVICE_TOKEN unset."""
        oracle = MarketplaceOracle()
        results = oracle.search_by_name("Иванов Иван")

        assert "phones" in results
        assert "emails" in results
        assert "listings" in results
        assert len(results["phones"]) >= 1
        assert results["phones"][0]["source"] == "avito"

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': ''})
    def test_demo_mode_by_phone(self):
        oracle = MarketplaceOracle()
        results = oracle.search_by_phone("+79161234567")

        assert len(results["phones"]) >= 1

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': ''})
    def test_demo_mode_search_all(self):
        oracle = MarketplaceOracle()
        results = oracle.search_all(
            full_name="Иванов Иван", phone="+79161234567",
        )

        assert len(results["phones"]) >= 1
        assert len(results["listings"]) >= 1

    def test_confidence_scores(self):
        """Confidence scores are correctly assigned per source."""
        oracle = MarketplaceOracle()
        assert oracle._CONFIDENCE["avito"] == 0.90
        assert oracle._CONFIDENCE["cian"] == 0.88
        assert oracle._CONFIDENCE["youla"] == 0.85
        assert oracle._CONFIDENCE["yandex_search"] == 0.70

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'real_token'})
    def test_real_mode_no_demo(self):
        """When VK_SERVICE_TOKEN is set, demo mode is not used."""
        oracle = MarketplaceOracle()
        assert not oracle._is_demo_mode()

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': ''})
    def test_demo_mode_enabled(self):
        oracle = MarketplaceOracle()
        assert oracle._is_demo_mode()

    def test_cities_collected_in_run_scanners(self):
        """City data from listings is collected for geo intelligence."""
        oracle = MarketplaceOracle(vk_token='test')

        # Mock all scanners to return empty results except one
        for scanner in oracle.scanners:
            scanner.search_by_name = MagicMock(
                return_value=ScannerResult(source=scanner.name)
            )

        # Make Avito return a listing with city
        avito_result = ScannerResult(source="avito")
        avito_result.listings.append(MarketplaceListing(
            title="Test", city="Санкт-Петербург", source="avito",
        ))
        oracle.scanners[0].search_by_name.return_value = avito_result

        results = oracle._run_scanners('name', full_name="Test")
        assert "cities" in results
        assert "Санкт-Петербург" in results["cities"]


# ── Playwright-Based Avito Tests ──────────────────────────────────

class TestAvitoPlaywright:
    """Test Playwright-based phone extraction from Avito listings."""

    def _make_mock_playwright_page(self, search_html, listing_html=None):
        """Create mock Playwright page for Avito flow."""
        page = MagicMock()

        # Track navigation history
        navigate_count = [0]

        def goto_side_effect(url, **kwargs):
            navigate_count[0] += 1
            return None

        page.goto.side_effect = goto_side_effect

        # Body inner_text returns search page text initially
        body_loc = MagicMock()
        body_loc.inner_text.return_value = search_html
        body_loc.count.return_value = 1

        def locator_side_effect(selector):
            loc = MagicMock()
            loc.count.return_value = 0
            loc.all.return_value = []

            if selector == 'body':
                return body_loc
            if 'data-marker="item"' in selector:
                # Search result items
                link = MagicMock()
                link.get_attribute.return_value = "/item/123456"
                loc.all.return_value = [link]
                return loc
            if 'h1' in selector:
                loc.count.return_value = 1
                loc.first = MagicMock()
                loc.first.inner_text.return_value = "iPhone 13 Pro Max"
                return loc
            if 'seller' in selector:
                loc.count.return_value = 1
                loc.first = MagicMock()
                loc.first.inner_text.return_value = "Иванов Иван"
                return loc
            if 'geo' in selector or 'address' in selector:
                loc.count.return_value = 1
                loc.first = MagicMock()
                loc.first.inner_text.return_value = "Москва"
                return loc
            if 'price' in selector:
                loc.count.return_value = 1
                loc.first = MagicMock()
                loc.first.inner_text.return_value = "75 000 ₽"
                return loc
            if 'phone-button' in selector or 'Показать' in selector:
                loc.count.return_value = 1
                loc.first = MagicMock()
                return loc
            if 'phone' in selector and 'button' not in selector:
                loc.count.return_value = 1
                loc.first = MagicMock()
                loc.first.inner_text.return_value = "+7 (916) 123-45-67"
                return loc
            if 'tel:' in selector:
                loc.count.return_value = 1
                loc.first = MagicMock()
                loc.first.get_attribute.return_value = "tel:+79161234567"
                return loc
            return loc

        page.locator.side_effect = locator_side_effect
        page.set_default_timeout.return_value = None
        page.add_init_script.return_value = None
        page.on.return_value = None
        page.content.return_value = "<html></html>"

        return page

    @patch('app.services.phase2.marketplace_scanner.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.marketplace_scanner.sync_playwright')
    @patch('app.services.phase2.marketplace_scanner.time')
    def test_avito_playwright_search(self, mock_time, mock_pw):
        """Avito Playwright search finds listings and extracts phones."""
        mock_time.sleep = MagicMock()
        mock_time.uniform = MagicMock(return_value=3.0)

        page = self._make_mock_playwright_page("Результаты поиска")

        # Set up playwright mock chain
        context = MagicMock()
        context.new_page.return_value = page
        browser = MagicMock()
        browser.new_context.return_value = context
        pw = MagicMock()
        pw.chromium.launch.return_value = browser
        pw_ctx = MagicMock()
        pw_ctx.__enter__ = MagicMock(return_value=pw)
        pw_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw.return_value = pw_ctx

        scanner = AvitoScanner()
        result = scanner.search_by_name("Иванов Иван")

        assert result.source == "avito"
        # Should have extracted the phone via Playwright
        assert len(result.phones_found) >= 1 or len(result.listings) >= 1

    @patch('app.services.phase2.marketplace_scanner.PLAYWRIGHT_AVAILABLE', True)
    @patch('app.services.phase2.marketplace_scanner.sync_playwright')
    @patch('app.services.phase2.marketplace_scanner.time')
    def test_avito_antibot_detection(self, mock_time, mock_pw):
        """Avito anti-bot detection gracefully handled."""
        mock_time.sleep = MagicMock()
        mock_time.uniform = MagicMock(return_value=3.0)

        page = self._make_mock_playwright_page("captcha доступ ограничен")

        context = MagicMock()
        context.new_page.return_value = page
        browser = MagicMock()
        browser.new_context.return_value = context
        pw = MagicMock()
        pw.chromium.launch.return_value = browser
        pw_ctx = MagicMock()
        pw_ctx.__enter__ = MagicMock(return_value=pw)
        pw_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw.return_value = pw_ctx

        scanner = AvitoScanner()
        result = scanner.search_by_name("Test")

        assert "anti-bot" in str(result.errors).lower() or len(result.phones_found) == 0

    def test_max_deep_listings_attribute(self):
        """AvitoScanner has MAX_DEEP_LISTINGS configured."""
        assert AvitoScanner.MAX_DEEP_LISTINGS == 5


# ── Integration: Contact Discovery Wiring ─────────────────────────

class TestMarketplaceContactDiscoveryIntegration:
    """Verify marketplace scanner is properly wired into Stage 4."""

    def test_marketplace_confidence_score_in_contact_discovery(self):
        """CONFIDENCE_SCORES has marketplace key."""
        from app.services.candidate.contact_discovery import CONFIDENCE_SCORES
        assert 'marketplace' in CONFIDENCE_SCORES
        assert CONFIDENCE_SCORES['marketplace'] == 0.90

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': ''})
    def test_demo_mode_produces_phones(self):
        """Demo mode marketplace scan produces phone contacts."""
        oracle = MarketplaceOracle()
        results = oracle.search_all(full_name="Тестов Тест")
        assert len(results["phones"]) >= 1
        for p in results["phones"]:
            assert "number" in p
            assert "source" in p
            assert "confidence" in p


# ── Parameterized: 6 Scanner Names ───────────────────────────────

SCANNER_NAMES = ["avito", "youla", "cian", "auto_ru", "yandex_search", "vk_market"]


@pytest.mark.parametrize("scanner_name", SCANNER_NAMES)
def test_scanner_exists_in_oracle(scanner_name):
    """Each scanner is registered in MarketplaceOracle."""
    oracle = MarketplaceOracle(vk_token='test')
    names = [s.name for s in oracle.scanners]
    assert scanner_name in names


@pytest.mark.parametrize("scanner_name", SCANNER_NAMES)
def test_scanner_has_confidence(scanner_name):
    """Each scanner has a confidence score defined."""
    oracle = MarketplaceOracle()
    assert scanner_name in oracle._CONFIDENCE
    assert 0.0 < oracle._CONFIDENCE[scanner_name] <= 1.0
