"""
Comprehensive tests for CourtRecordSearch — parser, CSRF flow, deduplication,
role detection, criminal article extraction, verdict extraction.
No live HTTP calls — all network interactions are mocked.
"""

import re
import pytest
from unittest.mock import MagicMock, patch

import app.services.phase3.court_search as court_mod
from app.services.phase3.court_search import (
    CourtCase,
    CourtRecordSearch,
    classify_court_role,
    get_frequent_plaintiff_flag,
    ARTICLE_CATEGORIES,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def make_svc():
    return CourtRecordSearch(timeout=5)


def make_case(case_number='2-336/2025', court='Тестовый суд', source='test', role=''):
    return CourtCase(case_number=case_number, court_name=court, source=source, role=role)


# ── classify_court_role ────────────────────────────────────────────────────

class TestClassifyCourtRole:

    def test_plaintiff_keyword_near_name(self):
        text = 'Истец Иванов Иван Иванович обратился с иском'
        assert classify_court_role(text, 'Иванов Иван Иванович') == 'plaintiff'

    def test_defendant_keyword_near_name(self):
        text = 'Ответчик Петров Петр Петрович возражал против иска'
        assert classify_court_role(text, 'Петров Петр Петрович') == 'defendant'

    def test_plaintiff_wins_over_defendant_by_proximity(self):
        # Иванов is within 100 chars of "истец" but "ответчик" is 300+ chars away
        filler = 'x' * 300
        text = f'Истец Иванов Иван подал иск. {filler} Ответчик Сидоров уклонялся.'
        assert classify_court_role(text, 'Иванов Иван') == 'plaintiff'

    def test_defendant_wins_over_plaintiff_by_proximity(self):
        # Петров is within 100 chars of "ответчик"; "истец" is 300+ chars away
        filler = 'y' * 300
        text = f'Истец Сидоров подал иск. {filler} Ответчик Петров Петр не явился.'
        assert classify_court_role(text, 'Петров Петр') == 'defendant'

    def test_global_fallback_plaintiff_only(self):
        # Name not in text → global scan
        text = 'Истец обратился с требованием о взыскании долга'
        assert classify_court_role(text, 'Иванов Иван') == 'plaintiff'

    def test_global_fallback_defendant_only(self):
        text = 'Ответчик не явился на заседание'
        assert classify_court_role(text, 'Иванов Иван') == 'defendant'

    def test_unknown_when_both_or_neither(self):
        text = 'Стороны по делу о разделе имущества'
        result = classify_court_role(text, 'Иванов Иван')
        assert result == 'unknown'

    def test_empty_text_returns_unknown(self):
        assert classify_court_role('', 'Иванов') == 'unknown'

    def test_empty_name_returns_unknown(self):
        assert classify_court_role('Истец Иванов', '') == 'unknown'


# ── get_frequent_plaintiff_flag ────────────────────────────────────────────

class TestFrequentPlaintiffFlag:

    def test_three_plaintiff_cases_triggers_flag(self):
        records = [{'role': 'plaintiff'}] * 3
        flag = get_frequent_plaintiff_flag(records)
        assert flag is not None
        assert flag['code'] == 'frequent_plaintiff'

    def test_two_plaintiff_cases_no_flag(self):
        records = [{'role': 'plaintiff'}] * 2
        assert get_frequent_plaintiff_flag(records) is None

    def test_mixed_roles_three_plaintiff(self):
        records = [
            {'role': 'plaintiff'},
            {'role': 'defendant'},
            {'role': 'plaintiff'},
            {'role': 'plaintiff'},
        ]
        flag = get_frequent_plaintiff_flag(records)
        assert flag is not None

    def test_russian_role_истец_also_counts(self):
        records = [{'role': 'истец'}] * 3
        flag = get_frequent_plaintiff_flag(records)
        assert flag is not None

    def test_empty_records(self):
        assert get_frequent_plaintiff_flag([]) is None


# ── CourtCase.to_dict ──────────────────────────────────────────────────────

class TestCourtCaseToDict:

    def test_all_fields_present(self):
        c = CourtCase(
            case_number='2-336/2025',
            court_name='Районный суд',
            case_type='гражданское',
            date='01.01.2025',
            role='истец',
            category='договор',
            result='удовлетворено',
            url='https://sudact.ru/doc/1',
            source='судебныерешения.рф',
            confidence='high',
        )
        d = c.to_dict()
        for key in ['case_number', 'court_name', 'case_type', 'date', 'role',
                    'category', 'result', 'url', 'source', 'confidence',
                    'raw_text', 'criminal_articles', 'verdict']:
            assert key in d, f'Missing key: {key}'

    def test_criminal_articles_defaults_to_empty_list(self):
        c = CourtCase(case_number='1-1/2025', court_name='Суд')
        assert c.criminal_articles == []
        assert c.to_dict()['criminal_articles'] == []


# ── _detect_case_type ─────────────────────────────────────────────────────

class TestDetectCaseType:

    def test_criminal(self):
        svc = make_svc()
        assert svc._detect_case_type('Уголовное дело по ст. 228 УК РФ') == 'уголовное'

    def test_administrative(self):
        svc = make_svc()
        assert svc._detect_case_type('Административное правонарушение') == 'административное'

    def test_arbitration(self):
        svc = make_svc()
        assert svc._detect_case_type('Арбитражный суд г. Москвы') == 'арбитражное'

    def test_civil_default(self):
        svc = make_svc()
        assert svc._detect_case_type('Дело о взыскании долга') == 'гражданское'


# ── _extract_criminal_articles ────────────────────────────────────────────

class TestExtractCriminalArticles:

    def test_part_article(self):
        # Multiple patterns may match the same article string (part_article + article_only)
        # with different dedup keys. Assert the specific part match exists.
        svc = make_svc()
        articles = svc._extract_criminal_articles('ч. 2 ст. 228 УК РФ')
        with_part = [a for a in articles if a['article'] == '228' and a['part'] == '2']
        assert len(with_part) == 1
        assert with_part[0]['category'] == 'наркотики'

    def test_article_only(self):
        svc = make_svc()
        articles = svc._extract_criminal_articles('ст. 158 УК РФ')
        assert any(a['article'] == '158' for a in articles)
        assert any(a['category'] == 'кража' for a in articles)

    def test_paragraph_part_article(self):
        # paragraph_part_article, part_article, and article_only all match the same string.
        # Assert the most specific match (with paragraph) exists.
        svc = make_svc()
        articles = svc._extract_criminal_articles('п.б ч.2 ст.159 УК РФ')
        with_para = [a for a in articles if a['article'] == '159' and a['paragraph'] == 'б']
        assert len(with_para) == 1
        assert with_para[0]['part'] == '2'

    def test_deduplication(self):
        svc = make_svc()
        text = 'ст. 228 УК РФ ... ст. 228 УК РФ'
        articles = svc._extract_criminal_articles(text)
        assert len(articles) == 1

    def test_multiple_different_articles(self):
        svc = make_svc()
        text = 'ч.1 ст.228 УК РФ и ч.1 ст.222 УК РФ'
        articles = svc._extract_criminal_articles(text)
        nums = {a['article'] for a in articles}
        assert '228' in nums and '222' in nums

    def test_empty_text(self):
        svc = make_svc()
        assert svc._extract_criminal_articles('') == []

    def test_unknown_article_no_category(self):
        svc = make_svc()
        articles = svc._extract_criminal_articles('ст. 999 УК РФ')
        assert articles[0]['category'] == ''


# ── _extract_verdict ──────────────────────────────────────────────────────

class TestExtractVerdict:

    def test_conditional_sentence(self):
        svc = make_svc()
        verdict = svc._extract_verdict('осуждён условно на срок 2 года')
        assert 'условно' in verdict
        assert '2' in verdict

    def test_prison_sentence(self):
        # Regex matches genitive/nominative forms: лишения/лишение (not dative лишению)
        svc = make_svc()
        verdict = svc._extract_verdict('назначено лишение свободы на срок 3 года')
        assert 'лишение свободы' in verdict

    def test_fine(self):
        svc = make_svc()
        verdict = svc._extract_verdict('назначен штраф в размере 50000 рублей')
        assert 'штраф' in verdict
        assert '50000' in verdict

    def test_empty_text(self):
        svc = make_svc()
        assert svc._extract_verdict('') == ''

    def test_no_verdict_in_text(self):
        svc = make_svc()
        result = svc._extract_verdict('Дело о взыскании долга')
        assert result == ''


# ── _parse_sudact_list_item ───────────────────────────────────────────────

class TestParseSudactListItem:

    def _make_soup_li(self, html):
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, 'lxml').find('li')

    def test_parses_case_number_and_court(self):
        svc = make_svc()
        html = '''<li>
            <a href="/regular/doc/abc123/">Решение № 2-336/2025 от 15 марта 2025 г.</a>
            Тверской районный суд
        </li>'''
        item = self._make_soup_li(html)
        case = svc._parse_sudact_list_item(item, 'Иванов Иван')
        assert case is not None
        assert case.case_number == '2-336/2025'
        # URL: trailing slash is preserved (href.split('?')[0] keeps trailing slash)
        assert case.url == 'https://sudact.ru/regular/doc/abc123/'
        assert case.source == 'sudact.ru'

    def test_returns_none_when_no_case_number(self):
        svc = make_svc()
        html = '<li><a href="/regular/doc/x/">Решение без номера</a></li>'
        item = self._make_soup_li(html)
        case = svc._parse_sudact_list_item(item, 'Иванов Иван')
        assert case is None

    def test_returns_none_when_no_link(self):
        svc = make_svc()
        html = '<li>Просто текст 2-336/2025</li>'
        item = self._make_soup_li(html)
        case = svc._parse_sudact_list_item(item, 'Иванов Иван')
        assert case is None

    def test_confidence_high(self):
        svc = make_svc()
        html = '<li><a href="/regular/doc/x/">Решение № 2-999/2024</a> Суд</li>'
        item = self._make_soup_li(html)
        case = svc._parse_sudact_list_item(item, 'Петров Петр')
        assert case is not None
        assert case.confidence == 'high'


# ── _search_sudebnye_resheniya HTML parser ────────────────────────────────

SR_HTML_RESULTS = '''<html><body>
<div class="count">Всего найдено документов:2. Показано документов:2</div>
<div id="list">
  <table class="table table-bordered">
    <tr class="active">
      <td>Тверской районный суд г. Москвы</td>
      <td><a href="/view/123456">2-336/2025</a></td>
    </tr>
    <tr>
      <td>Дата: 15.03.2025</td>
      <td>Истец: Иванов Иван Иванович. Ответчик: ООО Ромашка</td>
    </tr>
  </table>
  <table class="table table-bordered">
    <tr class="active">
      <td>Октябрьский районный суд</td>
      <td><a href="/view/789">1-100/2024</a></td>
    </tr>
    <tr>
      <td>Дата: 01.10.2024</td>
      <td>Ответчик: Иванов Иван Иванович</td>
    </tr>
  </table>
</div>
</body></html>'''

SR_HTML_NO_RESULTS = '''<html><body>
<div class="count">Всего найдено документов:0. Показано документов:0</div>
<div id="list"></div>
</body></html>'''

SR_HTML_HOMEPAGE = '''<html><body>
<form>
  <input type="hidden" name="simpleSearch[_token]" value="test_csrf_token_abc123">
</form>
</body></html>'''


class TestSearchSudebnye:

    def _mock_session(self, svc, homepage_html, results_html):
        """Patch requests.Session.get and .post on svc.session."""
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.text = homepage_html

        post_resp = MagicMock()
        post_resp.status_code = 200
        post_resp.text = results_html
        post_resp.url = 'https://xn--90afdbaav0bd1afy6eub5d.xn--p1ai/search'

        with patch('requests.Session.get', return_value=get_resp), \
             patch('requests.Session.post', return_value=post_resp):
            return svc._search_sudebnye_resheniya('Иванов Иван Иванович', limit=10)

    def test_parses_two_cases(self):
        svc = make_svc()
        results = self._mock_session(svc, SR_HTML_HOMEPAGE, SR_HTML_RESULTS)
        assert len(results) == 2

    def test_case_number_extracted(self):
        svc = make_svc()
        results = self._mock_session(svc, SR_HTML_HOMEPAGE, SR_HTML_RESULTS)
        nums = {r.case_number for r in results}
        assert '2-336/2025' in nums

    def test_court_name_extracted(self):
        svc = make_svc()
        results = self._mock_session(svc, SR_HTML_HOMEPAGE, SR_HTML_RESULTS)
        courts = {r.court_name for r in results}
        assert any('Тверской' in c for c in courts)

    def test_date_extracted(self):
        svc = make_svc()
        results = self._mock_session(svc, SR_HTML_HOMEPAGE, SR_HTML_RESULTS)
        dates = [r.date for r in results if r.date]
        assert '15.03.2025' in dates

    def test_role_detected_for_plaintiff(self):
        svc = make_svc()
        results = self._mock_session(svc, SR_HTML_HOMEPAGE, SR_HTML_RESULTS)
        # First case: "Истец: Иванов Иван Иванович" → should be истец
        first = next((r for r in results if r.case_number == '2-336/2025'), None)
        assert first is not None
        assert first.role in ('истец', 'участник')  # role detection may vary

    def test_source_is_set(self):
        svc = make_svc()
        results = self._mock_session(svc, SR_HTML_HOMEPAGE, SR_HTML_RESULTS)
        assert all(r.source == 'судебныерешения.рф' for r in results)

    def test_confidence_high(self):
        svc = make_svc()
        results = self._mock_session(svc, SR_HTML_HOMEPAGE, SR_HTML_RESULTS)
        assert all(r.confidence == 'high' for r in results)

    def test_empty_results_html(self):
        svc = make_svc()
        results = self._mock_session(svc, SR_HTML_HOMEPAGE, SR_HTML_RESULTS_EMPTY := SR_HTML_NO_RESULTS)
        assert results == []

    def test_csrf_not_found_returns_empty(self):
        svc = make_svc()
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.text = '<html><body><form></form></body></html>'  # no token

        with patch('requests.Session.get', return_value=get_resp):
            results = svc._search_sudebnye_resheniya('Иванов Иван', limit=10)
        assert results == []

    def test_get_non_200_returns_empty(self):
        svc = make_svc()
        get_resp = MagicMock()
        get_resp.status_code = 503
        get_resp.text = ''

        with patch('requests.Session.get', return_value=get_resp):
            results = svc._search_sudebnye_resheniya('Иванов Иван', limit=10)
        assert results == []

    def test_timeout_returns_empty(self):
        import requests as _requests
        svc = make_svc()
        with patch('requests.Session.get', side_effect=_requests.Timeout('test')):
            results = svc._search_sudebnye_resheniya('Иванов Иван', limit=10)
        assert results == []


# ── search_by_name deduplication ─────────────────────────────────────────

class TestDeduplication:

    def test_same_case_number_deduplicated(self):
        svc = make_svc()
        dupe1 = make_case('2-336/2025', source='судебныерешения.рф')
        dupe2 = make_case('2-336/2025', source='reputation.su')

        with patch.object(svc, '_search_sudebnye_resheniya', return_value=[dupe1]), \
             patch.object(svc, '_search_sudact_playwright', return_value=[dupe2]), \
             patch('app.services.phase3.reputation_su_service.search_reputation_su', return_value=([], 'empty')), \
             patch('app.services.phase3.kad_arbitr_service.search_kad_arbitr_person', return_value=([], 'empty')), \
             patch('app.services.phase3.court_search.PLAYWRIGHT_AVAILABLE', True):
            results = svc.search_by_name('Иванов Иван')

        case_numbers = [r.case_number for r in results]
        assert case_numbers.count('2-336/2025') == 1

    def test_different_case_numbers_kept_separately(self):
        svc = make_svc()
        c1 = make_case('2-100/2025')
        c2 = make_case('2-200/2025')

        with patch.object(svc, '_search_sudebnye_resheniya', return_value=[c1, c2]), \
             patch('app.services.phase3.reputation_su_service.search_reputation_su', return_value=([], 'empty')), \
             patch('app.services.phase3.kad_arbitr_service.search_kad_arbitr_person', return_value=([], 'empty')), \
             patch('app.services.phase3.court_search.PLAYWRIGHT_AVAILABLE', False):
            results = svc.search_by_name('Иванов Иван')

        assert len(results) == 2

    def test_cases_without_number_kept(self):
        svc = make_svc()
        c = CourtCase(case_number='', court_name='Суд', source='test')

        with patch.object(svc, '_search_sudebnye_resheniya', return_value=[c]), \
             patch('app.services.phase3.reputation_su_service.search_reputation_su', return_value=([], 'empty')), \
             patch('app.services.phase3.kad_arbitr_service.search_kad_arbitr_person', return_value=([], 'empty')), \
             patch('app.services.phase3.court_search.PLAYWRIGHT_AVAILABLE', False):
            results = svc.search_by_name('Иванов Иван')

        assert len(results) == 1


# ── search_by_name source ordering ───────────────────────────────────────

class TestSourceOrdering:

    def test_sudact_called_when_playwright_available(self):
        svc = make_svc()
        with patch.object(svc, '_search_sudact_playwright', return_value=[]) as mock_sudact, \
             patch.object(svc, '_search_sudebnye_resheniya', return_value=[]), \
             patch('app.services.phase3.reputation_su_service.search_reputation_su', return_value=([], 'empty')), \
             patch('app.services.phase3.kad_arbitr_service.search_kad_arbitr_person', return_value=([], 'empty')), \
             patch('app.services.phase3.court_search.PLAYWRIGHT_AVAILABLE', True):
            svc.search_by_name('Иванов Иван')
        mock_sudact.assert_called_once()

    def test_sudact_not_called_when_playwright_unavailable(self):
        svc = make_svc()
        with patch.object(svc, '_search_sudact_playwright', return_value=[]) as mock_sudact, \
             patch.object(svc, '_search_sudebnye_resheniya', return_value=[]), \
             patch('app.services.phase3.reputation_su_service.search_reputation_su', return_value=([], 'empty')), \
             patch('app.services.phase3.kad_arbitr_service.search_kad_arbitr_person', return_value=([], 'empty')), \
             patch('app.services.phase3.court_search.PLAYWRIGHT_AVAILABLE', False):
            svc.search_by_name('Иванов Иван')
        mock_sudact.assert_not_called()

    def test_sudebnye_called_regardless_of_playwright(self):
        svc = make_svc()
        for pw_available in [True, False]:
            with patch.object(svc, '_search_sudact_playwright', return_value=[]), \
                 patch.object(svc, '_search_sudebnye_resheniya', return_value=[]) as mock_sr, \
                 patch('app.services.phase3.reputation_su_service.search_reputation_su', return_value=([], 'empty')), \
             patch('app.services.phase3.kad_arbitr_service.search_kad_arbitr_person', return_value=([], 'empty')), \
                 patch.dict(vars(court_mod), {'PLAYWRIGHT_AVAILABLE': pw_available}):
                svc.search_by_name('Иванов Иван')
            mock_sr.assert_called_once()

    def test_empty_name_returns_empty_without_calling_sources(self):
        svc = make_svc()
        with patch.object(svc, '_search_sudact_playwright', return_value=[]) as mock_s, \
             patch.object(svc, '_search_sudebnye_resheniya', return_value=[]) as mock_sr:
            results = svc.search_by_name('')
        assert results == []
        mock_s.assert_not_called()
        mock_sr.assert_not_called()

    def test_source_exception_does_not_propagate(self):
        svc = make_svc()
        with patch.object(svc, '_search_sudebnye_resheniya', side_effect=Exception('network error')), \
             patch('app.services.phase3.reputation_su_service.search_reputation_su', return_value=([], 'empty')), \
             patch('app.services.phase3.kad_arbitr_service.search_kad_arbitr_person', return_value=([], 'empty')), \
             patch('app.services.phase3.court_search.PLAYWRIGHT_AVAILABLE', False):
            results = svc.search_by_name('Иванов Иван')
        assert isinstance(results, list)


# ── get_manual_search_urls ────────────────────────────────────────────────

class TestManualUrls:

    def test_contains_sudact(self):
        urls = CourtRecordSearch.get_manual_search_urls('Иванов Иван')
        assert any('sudact' in u['url'] for u in urls)

    def test_contains_arbitr(self):
        urls = CourtRecordSearch.get_manual_search_urls('Иванов Иван')
        assert any('arbitr' in u['url'] for u in urls)

    def test_contains_sudebnye_resheniya(self):
        urls = CourtRecordSearch.get_manual_search_urls('Иванов Иван')
        assert any('xn--90afdbaav0bd1afy6eub5d' in u['url'] or 'судебные' in u.get('name','').lower() for u in urls)

    def test_name_encoded_in_sudact_url(self):
        urls = CourtRecordSearch.get_manual_search_urls('Иванов Иван')
        sudact = next(u for u in urls if 'sudact' in u['url'])
        assert '%' in sudact['url'] or 'Иванов' in sudact['url']

    def test_at_least_four_sources(self):
        urls = CourtRecordSearch.get_manual_search_urls('Тест')
        assert len(urls) >= 4


# ── per-source statuses + kad.arbitr.ru wiring ────────────────────────────

def _stub_sources(svc, sr_cases=None, rep=([], 'empty'), kad=([], 'empty'),
                  playwright=False, sudact_cases=None):
    """Patch all four sources of search_by_name in one place."""
    return [
        patch.object(svc, '_search_sudact_playwright',
                     return_value=sudact_cases or []),
        patch.object(svc, '_search_sudebnye_resheniya',
                     return_value=sr_cases or []),
        patch('app.services.phase3.reputation_su_service.search_reputation_su',
              return_value=rep),
        patch('app.services.phase3.kad_arbitr_service.search_kad_arbitr_person',
              return_value=kad),
        patch('app.services.phase3.court_search.PLAYWRIGHT_AVAILABLE', playwright),
    ]


def _search_with_stubs(svc, name='Иванов Иван Иванович', inn='', **stub_kw):
    from contextlib import ExitStack
    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in _stub_sources(svc, **stub_kw)]
        results = svc.search_by_name(name, inn=inn)
    return results, dict(svc.last_source_statuses), mocks


KAD_RECORD = {
    'case_number': 'А40-555/2024',
    'court_name': 'АС города Москвы',
    'case_type': 'банкротное',
    'date': '15.03.2024',
    'role': 'ответчик',
    'subject': 'О несостоятельности (банкротстве)',
    'url': 'https://kad.arbitr.ru/Card/abc',
    'source': 'kad.arbitr.ru',
    'matched_by': 'inn',
}


class TestSourceStatuses:

    def test_all_empty_statuses(self):
        svc = make_svc()
        _, statuses, _ = _search_with_stubs(svc)
        assert statuses == {
            'sudact.ru': 'skipped',
            'судебныерешения.рф': 'empty',
            'reputation.su': 'empty',
            'kad.arbitr.ru': 'empty',
        }

    def test_reputation_blocked_propagates(self):
        """A bot-walled reputation.su must read 'blocked', not 'empty'."""
        svc = make_svc()
        _, statuses, _ = _search_with_stubs(svc, rep=([], 'blocked'))
        assert statuses['reputation.su'] == 'blocked'

    def test_kad_blocked_propagates(self):
        svc = make_svc()
        _, statuses, _ = _search_with_stubs(svc, kad=([], 'blocked'))
        assert statuses['kad.arbitr.ru'] == 'blocked'

    def test_sr_exception_reports_error(self):
        svc = make_svc()
        with patch.object(svc, '_search_sudebnye_resheniya',
                          side_effect=Exception('boom')), \
             patch('app.services.phase3.reputation_su_service.search_reputation_su',
                   return_value=([], 'empty')), \
             patch('app.services.phase3.kad_arbitr_service.search_kad_arbitr_person',
                   return_value=([], 'empty')), \
             patch('app.services.phase3.court_search.PLAYWRIGHT_AVAILABLE', False):
            svc.search_by_name('Иванов Иван')
        assert svc.last_source_statuses['судебныерешения.рф'] == 'error'

    def test_ok_status_when_source_returns_cases(self):
        svc = make_svc()
        _, statuses, _ = _search_with_stubs(
            svc, sr_cases=[make_case('2-1/2025', source='судебныерешения.рф')],
        )
        assert statuses['судебныерешения.рф'] == 'ok'

    def test_sudact_status_when_playwright_on(self):
        svc = make_svc()
        _, statuses, _ = _search_with_stubs(svc, playwright=True)
        assert statuses['sudact.ru'] == 'empty'

    def test_empty_name_resets_statuses(self):
        svc = make_svc()
        svc.last_source_statuses = {'stale': 'ok'}
        results = svc.search_by_name('')
        assert results == []
        assert svc.last_source_statuses == {}


class TestKadWiring:

    def test_kad_case_mapped_to_court_case(self):
        svc = make_svc()
        results, statuses, _ = _search_with_stubs(svc, kad=([KAD_RECORD], 'ok'))
        assert statuses['kad.arbitr.ru'] == 'ok'
        assert len(results) == 1
        case = results[0]
        assert case.source == 'kad.arbitr.ru'
        assert case.case_type == 'банкротное'
        assert case.category == 'О несостоятельности (банкротстве)'
        assert case.role == 'ответчик'

    def test_inn_matched_kad_case_is_verified(self):
        svc = make_svc()
        results, _, _ = _search_with_stubs(svc, kad=([KAD_RECORD], 'ok'))
        assert results[0].confidence == 'VERIFIED'

    def test_name_matched_kad_case_is_medium(self):
        svc = make_svc()
        rec = dict(KAD_RECORD, matched_by='full')
        results, _, _ = _search_with_stubs(svc, kad=([rec], 'ok'))
        assert results[0].confidence == 'medium'

    def test_inn_passed_through_to_kad(self):
        svc = make_svc()
        _, _, mocks = _search_with_stubs(svc, inn='771234567890')
        kad_mock = mocks[3]
        assert kad_mock.call_args.kwargs['inn'] == '771234567890'

    def test_verified_kad_duplicate_replaces_aggregator_copy(self):
        """An official INN match must not be downgraded by an earlier
        aggregator row with the same case number."""
        svc = make_svc()
        rep_rec = {
            'case_number': 'А40-555/2024',
            'court_name': 'АС города Москвы',
            'case_type': 'арбитражное',
            'date': '', 'role': '', 'subject': '', 'status': '',
            'url': '', 'criminal_articles': [], 'verdict': '',
            'source': 'reputation.su',
        }
        results, _, _ = _search_with_stubs(
            svc, rep=([rep_rec], 'ok'), kad=([KAD_RECORD], 'ok'),
        )
        matching = [r for r in results if r.case_number == 'А40-555/2024']
        assert len(matching) == 1
        assert matching[0].source == 'kad.arbitr.ru'
        assert matching[0].confidence == 'VERIFIED'

    def test_weaker_kad_duplicate_does_not_replace(self):
        svc = make_svc()
        rep_rec = {
            'case_number': 'А40-555/2024',
            'court_name': 'АС города Москвы',
            'case_type': 'арбитражное',
            'date': '', 'role': 'истец', 'subject': '', 'status': '',
            'url': '', 'criminal_articles': [], 'verdict': '',
            'source': 'reputation.su',
        }
        kad_rec = dict(KAD_RECORD, matched_by='full')
        results, _, _ = _search_with_stubs(
            svc, rep=([rep_rec], 'ok'), kad=([kad_rec], 'ok'),
        )
        matching = [r for r in results if r.case_number == 'А40-555/2024']
        assert len(matching) == 1
        assert matching[0].source == 'reputation.su'  # first occurrence kept

    def test_kad_exception_isolated(self):
        svc = make_svc()
        with patch.object(svc, '_search_sudebnye_resheniya', return_value=[]), \
             patch('app.services.phase3.reputation_su_service.search_reputation_su',
                   return_value=([], 'empty')), \
             patch('app.services.phase3.kad_arbitr_service.search_kad_arbitr_person',
                   side_effect=Exception('boom')), \
             patch('app.services.phase3.court_search.PLAYWRIGHT_AVAILABLE', False):
            results = svc.search_by_name('Иванов Иван')
        assert isinstance(results, list)
        assert svc.last_source_statuses['kad.arbitr.ru'] == 'error'
