"""
Tests for TelegramDiscoveryService — Methods A, B, C and name scoring.

Covers:
- Service instantiation
- Username candidate generation
- Name scoring with ё/е normalization (BUG FIX)
- Cross-script matching (Cyrillic ↔ Latin)
- Method A with mocked t.me responses
- Method B candidate filtering
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from unittest.mock import patch, MagicMock
from app.services.phase1.telegram_discovery import TelegramDiscoveryService
from app.services.phase1.transliteration import transliterate


# ============================================================
# Instantiation
# ============================================================

def test_service_instantiation():
    """TelegramDiscoveryService can be instantiated."""
    svc = TelegramDiscoveryService()
    assert svc is not None
    assert svc._checker is not None
    svc.close()


# ============================================================
# Username Candidate Generation
# ============================================================

def test_generate_candidates_basic():
    """Username generation produces valid Telegram-style candidates."""
    svc = TelegramDiscoveryService()
    candidates = svc._generate_telegram_candidates('Артём', 'Козлов')
    svc.close()

    assert len(candidates) > 0
    # All candidates must be valid Telegram usernames: 5+ chars, letter-first
    for c in candidates:
        assert len(c) >= 5, f"Candidate '{c}' is too short"
        assert c[0].isalpha(), f"Candidate '{c}' doesn't start with a letter"

    # Should include common patterns (transliterated)
    lower_candidates = {c.lower() for c in candidates}
    # At least one of the standard patterns should be present
    has_pattern = any(
        p in lower_candidates
        for p in ['artyom_kozlov', 'kozlov_artyom', 'artem_kozlov', 'kozlov_artem']
    )
    assert has_pattern, f"No standard patterns found in: {lower_candidates}"


def test_generate_candidates_with_birth_year():
    """Birth year variants are added when birth_year is provided."""
    svc = TelegramDiscoveryService()
    candidates_with_year = svc._generate_telegram_candidates('Иван', 'Петров', birth_year=1990)
    svc.close()

    lower = {c.lower() for c in candidates_with_year}
    # Should contain year-suffixed variants
    has_year = any('90' in c or '1990' in c for c in lower)
    assert has_year, f"No year-suffixed candidates in: {lower}"


def test_generate_candidates_deduplication():
    """Candidate list has no duplicates."""
    svc = TelegramDiscoveryService()
    candidates = svc._generate_telegram_candidates('Дмитрий', 'Сидоров')
    svc.close()

    lower_candidates = [c.lower() for c in candidates]
    assert len(lower_candidates) == len(set(lower_candidates)), "Duplicate candidates found"


def test_generate_candidates_max_limit():
    """Candidate list respects MAX_USERNAME_CANDIDATES."""
    svc = TelegramDiscoveryService()
    candidates = svc._generate_telegram_candidates('Александр', 'Козлов', birth_year=1985)
    svc.close()

    assert len(candidates) <= svc.MAX_USERNAME_CANDIDATES


# ============================================================
# Name Scoring — ё/е normalization (BUG FIX)
# ============================================================

def test_score_yo_ye_single_word():
    """ё/е normalization: 'Артём' must match 'Артем' (single word)."""
    svc = TelegramDiscoveryService()
    result = svc._score_name_match('Артём', 'Козлов', 'Артем')
    svc.close()

    assert result['score'] > 0, "ё/е should match (was broken before fix)"
    assert result['match'] is True


def test_score_yo_ye_full_name():
    """ё/е normalization: 'Артём Козлов' must match 'Артем Козлов'."""
    svc = TelegramDiscoveryService()
    result = svc._score_name_match('Артём', 'Козлов', 'Артем Козлов')
    svc.close()

    assert result['score'] == 1.0, f"Full name with ё/е should score 1.0, got {result['score']}"
    assert result['method'] == 'full_name_exact'


def test_score_yo_ye_semyon():
    """ё/е normalization: 'Семён' must match 'Семен'."""
    svc = TelegramDiscoveryService()
    result = svc._score_name_match('Семён', 'Иванов', 'Семен Иванов')
    svc.close()

    assert result['score'] == 1.0


def test_score_yo_ye_reverse():
    """ё/е normalization works in both directions: target has е, display has ё."""
    svc = TelegramDiscoveryService()
    result = svc._score_name_match('Артем', 'Козлов', 'Артём Козлов')
    svc.close()

    assert result['score'] == 1.0


# ============================================================
# Name Scoring — standard cases
# ============================================================

def test_score_exact_match():
    """Exact full name match scores 1.0."""
    svc = TelegramDiscoveryService()
    result = svc._score_name_match('Артём', 'Козлов', 'Артём Козлов')
    svc.close()

    assert result['score'] == 1.0
    assert result['method'] == 'full_name_exact'


def test_score_cross_script_latin():
    """Latin display name matches Cyrillic target via transliteration."""
    svc = TelegramDiscoveryService()
    result = svc._score_name_match('Артём', 'Козлов', 'Artem Kozlov')
    svc.close()

    assert result['score'] >= 0.6, f"Cross-script should score >= 0.6, got {result['score']}"
    assert result['match'] is True


def test_score_diminutive():
    """Diminutive name variant matches (Александр ↔ Саша)."""
    svc = TelegramDiscoveryService()
    result = svc._score_name_match('Александр', 'Петров', 'Саша Петров')
    svc.close()

    assert result['match'] is True
    assert result['score'] >= 0.6


def test_score_no_match():
    """Completely different name scores low."""
    svc = TelegramDiscoveryService()
    result = svc._score_name_match('Артём', 'Козлов', 'Ольга Белкина')
    svc.close()

    assert result['score'] < 0.3


def test_score_empty_display():
    """Empty display name returns no_data."""
    svc = TelegramDiscoveryService()
    result = svc._score_name_match('Артём', 'Козлов', '')
    svc.close()

    assert result['score'] == 0.0
    assert result['method'] == 'no_data'


def test_score_first_name_only_cap():
    """Single-word display names are capped at 0.55 (first_name_only)."""
    svc = TelegramDiscoveryService()
    result = svc._score_name_match('Артём', 'Козлов', 'Артём')
    svc.close()

    assert result['score'] <= 0.55, f"Single-word should be capped, got {result['score']}"
    assert 'first_name_only' in result['method']


def test_score_emoji_in_display_name():
    """Emojis in display name are stripped before matching."""
    svc = TelegramDiscoveryService()
    result = svc._score_name_match('Артём', 'Козлов', 'Артём Козлов 🔥✨')
    svc.close()

    assert result['score'] == 1.0


# ============================================================
# Method B precision: guessed handle must match the candidate's name
# ============================================================

def _run_method_b(svc, display_name):
    """Run Method B with a single guessed candidate whose t.me account has
    the given display name. Returns the list of attributed profiles."""
    from app.services.phase2.telegram_crossref import TelegramProfile
    profile = TelegramProfile(
        exists=True, is_personal=True, username='ivan_petrov',
        display_name=display_name,
    )
    with patch.object(svc, '_generate_telegram_candidates', return_value=['ivan_petrov']), \
         patch.object(svc, '_check_username_web_fast', return_value=profile):
        return svc._method_b_username_guessing('Иван', 'Петров', set())


def test_method_b_drops_name_mismatch():
    """A GUESSED handle whose owner has a different name is a false positive
    (no provenance link to the candidate) and must NOT be attributed."""
    svc = TelegramDiscoveryService()
    try:
        results = _run_method_b(svc, 'Ольга Белкина')  # score < 0.3
    finally:
        svc.close()
    assert results == []


def test_method_b_keeps_full_name_match():
    """A guessed handle whose owner's name matches the candidate is kept."""
    svc = TelegramDiscoveryService()
    try:
        results = _run_method_b(svc, 'Иван Петров')  # score >= 0.6
    finally:
        svc.close()
    assert len(results) == 1
    assert results[0].get('confidence') in ('высокая', 'high')


def test_method_b_keeps_partial_name_match():
    """A partial (first-name-only) match is still plausible and kept as medium."""
    svc = TelegramDiscoveryService()
    try:
        results = _run_method_b(svc, 'Иван')  # first-name-only, 0.3 <= score
    finally:
        svc.close()
    assert len(results) == 1
    assert results[0].get('confidence') in ('средняя', 'medium')


# ============================================================
# Helpers
# ============================================================

def test_clean_display_name():
    """Display name cleaning removes emojis, keeps letters and hyphens."""
    svc = TelegramDiscoveryService()

    assert svc._clean_display_name('Артём Козлов 🔥') == 'Артём Козлов'
    assert svc._clean_display_name('Pavel ✅ Durov') == 'Pavel Durov'
    assert svc._clean_display_name('Анна-Мария') == 'Анна-Мария'
    assert svc._clean_display_name('  multiple   spaces  ') == 'multiple spaces'

    svc.close()


def test_basic_translit():
    """Basic transliteration covers common Cyrillic characters."""
    assert transliterate('козлов') == 'kozlov'
    assert transliterate('артём') == 'artem'  # shared module maps ё→e (GOST simple)
    assert transliterate('щукина') == 'shchukina'


def test_normalize_yo():
    """ё→е normalization helper works correctly."""
    svc = TelegramDiscoveryService()

    assert svc._normalize_yo('Артём') == 'Артем'
    assert svc._normalize_yo('Семён') == 'Семен'
    assert svc._normalize_yo('Ёлка') == 'Елка'
    assert svc._normalize_yo('Козлов') == 'Козлов'  # No ё, unchanged

    svc.close()


# ============================================================
# Method A: VK Cross-Reference (mocked)
# ============================================================

def test_method_a_skips_empty():
    """Method A returns empty list when no VK screen_names provided."""
    svc = TelegramDiscoveryService()
    result = svc._method_a_vk_crossref([], 'Артём', 'Козлов')
    svc.close()

    assert result == []


def test_method_a_skips_numeric_ids():
    """Method A skips VK numeric IDs (id123456)."""
    svc = TelegramDiscoveryService()

    # Mock the checker to avoid real HTTP requests
    mock_profile = MagicMock()
    mock_profile.exists = True
    mock_profile.is_personal = True
    mock_profile.display_name = 'Артём Козлов'
    mock_profile.username = 'artem_kozlov'
    mock_profile.bio = ''
    mock_profile.photo_url = None
    mock_profile.phones_in_bio = []

    with patch.object(svc._checker, 'check_username_web', return_value=mock_profile):
        result = svc._method_a_vk_crossref(
            ['id123456', 'id789'], 'Артём', 'Козлов'
        )

    svc.close()
    # Both are numeric IDs, both should be skipped
    assert result == []


def test_method_a_finds_matching_profile():
    """Method A returns profile when VK screen_name exists on Telegram with matching name."""
    svc = TelegramDiscoveryService()

    mock_profile = MagicMock()
    mock_profile.exists = True
    mock_profile.is_personal = True
    mock_profile.display_name = 'Артём Козлов'
    mock_profile.username = 'artem_kozlov'
    mock_profile.bio = 'Developer'
    mock_profile.photo_url = 'https://example.com/photo.jpg'
    mock_profile.phones_in_bio = []

    with patch.object(svc._checker, 'check_username_web', return_value=mock_profile):
        result = svc._method_a_vk_crossref(
            ['artem_kozlov'], 'Артём', 'Козлов'
        )

    svc.close()

    assert len(result) == 1
    assert result[0]['username'] == 'artem_kozlov'
    assert result[0]['platform'] == 'telegram'
    assert result[0]['confidence'] == 'высокая'


# ============================================================
# Method C: Telethon session file check
# ============================================================

def test_method_c_skips_without_credentials():
    """Method C returns empty list when Telegram credentials are missing."""
    svc = TelegramDiscoveryService()

    with patch.dict(os.environ, {
        'TELEGRAM_API_ID': '',
        'TELEGRAM_API_HASH': '',
        'TELEGRAM_PHONE': '',
    }):
        result = svc._method_c_telethon_search('Артём', 'Козлов', set())

    svc.close()
    assert result == []


def test_method_c_skips_without_session_file():
    """Method C returns empty list when session file doesn't exist."""
    svc = TelegramDiscoveryService()

    with patch.dict(os.environ, {
        'TELEGRAM_API_ID': '12345',
        'TELEGRAM_API_HASH': 'abc123',
        'TELEGRAM_PHONE': '+79001234567',
    }):
        with patch('os.path.exists', return_value=False):
            result = svc._method_c_telethon_search('Артём', 'Козлов', set())

    svc.close()
    assert result == []
