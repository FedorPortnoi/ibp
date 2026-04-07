"""Tests for reputation.su parser — court_name and subject extraction."""
import pytest
from app.services.phase3.reputation_su_service import _parse_cards


# Sample HTML mimicking the structure of a reputation.su search result card.
HTML_WITH_COURT_LI = """
<html><body>
<div class="srch-card__affairs-box">
    <h3>2-2300/2023</h3>
    <ul>
        <li><span>Категория</span><p>Гражданские</p></li>
        <li><span>Регистрация</span><p>09.12.2022</p></li>
        <li><span>Статус</span><p>Рассмотрено</p></li>
        <li><span>Суд</span><p>Краснодарский краевой суд</p></li>
        <li><span>Предмет</span><p>Взыскание задолженности по договору займа</p></li>
        <li><span>Ответчики</span><p class="srch-rp-card__company">Иванов Иван Иванович</p></li>
    </ul>
    <a href="/sudrf/123456">Посмотреть дело</a>
</div>
</body></html>
"""

HTML_WITH_NO_COURT = """
<html><body>
<div class="srch-card__affairs-box">
    <h3>1-500/2023</h3>
    <ul>
        <li><span>Категория</span><p>Уголовные</p></li>
        <li><span>Регистрация</span><p>15.03.2023</p></li>
        <li><span>Статус</span><p>В производстве</p></li>
        <li><span>Ответчики</span><p class="srch-rp-card__company">Иванов Иван Иванович</p></li>
    </ul>
    <a href="/sudrf/654321">Посмотреть дело</a>
</div>
</body></html>
"""

HTML_WITH_COURT_IN_TEXT = """
<html><body>
<div class="srch-card__affairs-box">
    <h3>2-100/2024</h3>
    <ul>
        <li><span>Категория</span><p>Гражданские</p></li>
        <li><span>Регистрация</span><p>01.02.2024</p></li>
        <li><span>Статус</span><p>Рассмотрено</p></li>
        <li><span>Ответчики</span><p class="srch-rp-card__company">Иванов Иван Иванович</p></li>
    </ul>
    <p>Дело рассмотрено в Тверской районный суд города Москвы в январе.</p>
    <a href="/sudrf/111111">Посмотреть дело</a>
</div>
</body></html>
"""


def test_reputation_court_name_extracted_from_li():
    """court_name извлекается из <li><span>Суд</span></li>."""
    cases = _parse_cards(HTML_WITH_COURT_LI, "Иванов Иван Иванович")
    assert len(cases) == 1
    case = cases[0]
    assert case['court_name'] == 'Краснодарский краевой суд'
    assert case['case_number'] == '2-2300/2023'


def test_reputation_subject_extracted_from_li():
    """subject извлекается из <li><span>Предмет</span></li>."""
    cases = _parse_cards(HTML_WITH_COURT_LI, "Иванов Иван Иванович")
    assert len(cases) == 1
    case = cases[0]
    assert case['subject'] == 'Взыскание задолженности по договору займа'


def test_reputation_empty_court_fallback_string():
    """Если court_name не найден — возвращается 'Суд не определён', не пустая строка."""
    cases = _parse_cards(HTML_WITH_NO_COURT, "Иванов Иван Иванович")
    assert len(cases) == 1
    case = cases[0]
    # Must never be empty — either extracted or fallback
    assert case['court_name'] != ''
    assert case['court_name'] is not None
    # Either an extracted value OR the fallback literal
    assert case['court_name'] == 'Суд не определён'


def test_reputation_court_regex_fallback():
    """court_name извлекается регексом из текста карточки если нет явного <li>."""
    cases = _parse_cards(HTML_WITH_COURT_IN_TEXT, "Иванов Иван Иванович")
    assert len(cases) == 1
    case = cases[0]
    # Should match "Тверской районный суд"
    assert 'суд' in case['court_name'].lower()
    assert case['court_name'] != 'Суд не определён'


def test_reputation_case_has_required_keys():
    """Каждая запись содержит ключи court_name и subject."""
    cases = _parse_cards(HTML_WITH_COURT_LI, "Иванов Иван Иванович")
    assert len(cases) == 1
    case = cases[0]
    assert 'court_name' in case
    assert 'subject' in case
    assert 'case_number' in case
    assert 'source' in case
    assert case['source'] == 'reputation.su'


def test_reputation_empty_html_returns_empty():
    """Пустой HTML не падает — возвращает []."""
    cases = _parse_cards("<html><body></body></html>", "Иванов Иван Иванович")
    assert cases == []
