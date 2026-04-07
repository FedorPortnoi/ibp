"""Tests for reputation.su deep parse — criminal_articles and verdict extraction."""
from unittest.mock import patch, MagicMock

import pytest

from app.services.phase3.reputation_su_service import (
    _deep_parse_records,
    _extract_criminal_articles,
    _fetch_reputation_case_details,
)


def test_extract_criminal_articles_reputation():
    """_extract_criminal_articles находит статьи в типичном тексте reputation.su."""
    sample_text = (
        "Гражданин Иванов И.И. признан виновным по ч.2 ст.228 УК РФ и осуждён "
        "к лишению свободы сроком на 3 года условно. Также вменяется "
        "п.в ч.2 ст.158 УК РФ."
    )
    articles = _extract_criminal_articles(sample_text)
    assert isinstance(articles, list)
    # All entries are strings (per spec) — not dicts
    assert all(isinstance(a, str) for a in articles)
    joined = ' '.join(articles)
    assert '228' in joined
    assert '158' in joined


def test_extract_criminal_articles_dedup():
    """Повторные совпадения дедуплицируются."""
    sample_text = "ст.228 УК РФ. Повторно: ст.228 УК РФ. И ст.228 УК РФ ещё раз."
    articles = _extract_criminal_articles(sample_text)
    # ст.228 УК РФ should appear only once after dedup
    assert sum(1 for a in articles if 'ст.228' in a.lower() or 'ст. 228' in a.lower()) >= 1
    assert len([a for a in articles if a.lower().startswith('ст.228')]) <= 1


def test_extract_criminal_articles_empty_text():
    """Пустой текст возвращает пустой список."""
    assert _extract_criminal_articles("") == []
    assert _extract_criminal_articles(None) == []


def test_extract_criminal_articles_no_matches():
    """Текст без УК РФ возвращает пустой список."""
    assert _extract_criminal_articles("Гражданское дело о взыскании задолженности.") == []


def test_fetch_reputation_case_details_failure():
    """При недоступном URL — возвращает пустую строку, не падает."""
    # Empty URL
    assert _fetch_reputation_case_details("") == ""
    # None
    assert _fetch_reputation_case_details(None) == ""


def test_fetch_reputation_case_details_request_exception():
    """RequestException не пробрасывается, возвращается пустая строка."""
    with patch('app.services.phase3.reputation_su_service.requests.get') as mock_get:
        mock_get.side_effect = Exception("network down")
        result = _fetch_reputation_case_details("https://reputation.su/sudrf/123")
        assert result == ""


def test_fetch_reputation_case_details_http_404():
    """HTTP 404 возвращает пустую строку, не падает."""
    with patch('app.services.phase3.reputation_su_service.requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp
        result = _fetch_reputation_case_details("https://reputation.su/sudrf/missing")
        assert result == ""


def test_fetch_reputation_case_details_success():
    """Успешный фетч возвращает текст без скриптов/стилей."""
    html = """
    <html>
    <head><script>var x = 1;</script><style>.a{color:red}</style></head>
    <body>
    <nav>NAV</nav>
    <main>Иванов И.И. осуждён по ч.2 ст.228 УК РФ к лишению свободы.</main>
    <footer>FOOTER</footer>
    </body></html>
    """
    with patch('app.services.phase3.reputation_su_service.requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_get.return_value = mock_resp
        result = _fetch_reputation_case_details("https://reputation.su/sudrf/123")
        assert 'Иванов' in result
        assert 'ч.2 ст.228 УК РФ' in result
        assert 'NAV' not in result
        assert 'FOOTER' not in result
        assert 'var x' not in result


def test_deep_parse_adds_criminal_articles():
    """После _deep_parse_records запись содержит criminal_articles и verdict."""
    records = [
        {
            'case_number': '1-100/2023',
            'court_name': 'Some Court',
            'url': 'https://reputation.su/sudrf/12345',
            'criminal_articles': [],
        }
    ]

    fake_text = (
        "Иванов И.И. признан виновным по ч.2 ст.228 УК РФ. "
        "Назначить наказание: лишение свободы сроком 3 года условно с испытательным сроком 2 года."
    )

    with patch(
        'app.services.phase3.reputation_su_service._fetch_reputation_case_details',
        return_value=fake_text,
    ):
        _deep_parse_records(records)

    assert records[0]['criminal_articles'], "criminal_articles should be populated"
    assert any('228' in a for a in records[0]['criminal_articles'])
    assert records[0].get('verdict')  # something extracted (verdict pattern matched)


def test_deep_parse_skips_records_without_url():
    """Записи без url пропускаются и не падают."""
    records = [{'case_number': '2-1/2023', 'url': '', 'criminal_articles': []}]
    _deep_parse_records(records)
    # No mutations expected
    assert records[0]['criminal_articles'] == []


def test_deep_parse_skips_already_enriched():
    """Записи уже с criminal_articles не перезаписываются."""
    pre = ['ст.158 УК РФ']
    records = [
        {
            'case_number': '1-2/2023',
            'url': 'https://reputation.su/sudrf/999',
            'criminal_articles': list(pre),
        }
    ]
    with patch(
        'app.services.phase3.reputation_su_service._fetch_reputation_case_details',
        return_value="ст.228 УК РФ",
    ):
        _deep_parse_records(records)
    assert records[0]['criminal_articles'] == pre
