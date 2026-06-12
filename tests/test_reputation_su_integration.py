"""
Integration tests for reputation.su:
- search_reputation_su (mocked HTTP) — (cases, status) contract
- bot-wall detection: 'blocked' must never look like a clean record
- deep-parse budget and prioritization
- CourtCase conversion in court_search (no data loss)
"""

from unittest.mock import patch, MagicMock
import pytest

from app.services.phase3.reputation_su_service import (
    search_reputation_su,
    _parse_cards,
    _is_blocked_page,
    _deep_parse_records,
    _fetch_reputation_case_details,
)


# ── HTML fixtures ─────────────────────────────────────────────────────────

CLOUDFLARE_CHALLENGE = '<html><head><title>Just a moment...</title></head><body>Click to continue</body></html>'

DDOS_GUARD_PAGE = '<html><body><div id="ddos-guard">Checking your browser</div></body></html>'

# Tiny 200-response without markers and without cards — proxy stub or an
# unknown interstitial; must be treated as blocked, not as "no cases".
TINY_PAGE = '<html><body>ok</body></html>'

# Realistic "no results" page: Nuxt shell is large even with zero cards.
EMPTY_RESULTS_HTML = (
    '<html><body><div id="__nuxt"><div class="search-page">'
    + '<span class="filler">x</span>' * 200
    + '</div></div></body></html>'
)

REPUTATION_HTML = """<html><body>
<div class="srch-card__affairs-box">
  <h3>1-228/2023</h3>
  <ul>
    <li><span>Категория</span><p>Уголовные</p></li>
    <li><span>Регистрация</span><p>12.01.2023</p></li>
    <li><span>Статус</span><p>Рассмотрено</p></li>
    <li><span>Суд</span><p>Тверской районный суд г. Москвы</p></li>
    <li><span>Предмет</span><p>Незаконный оборот наркотиков</p></li>
    <li><span>Ответчики</span><p class="srch-rp-card__company">Иванов Иван Иванович</p></li>
  </ul>
  <a href="/sudrf/99999">Посмотреть дело</a>
</div>
<div class="srch-card__affairs-box">
  <h3>2-500/2022</h3>
  <ul>
    <li><span>Категория</span><p>Гражданские</p></li>
    <li><span>Регистрация</span><p>03.05.2022</p></li>
    <li><span>Статус</span><p>В производстве</p></li>
    <li><span>Суд</span><p>Арбитражный суд г. Москвы</p></li>
    <li><span>Истцы</span><p class="srch-rp-card__company">Иванов Иван Иванович</p></li>
  </ul>
  <a href="/sudrf/88888">Посмотреть дело</a>
</div>
</body></html>"""


def _mock_get(html, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = html
    return resp


def _run_search(html=None, status=200, side_effect=None, name='Иванов Иван Иванович',
                deep_parse=False):
    """Run search_reputation_su with a mocked Session.

    Returns (cases, status_str, session_mock).
    """
    with patch('app.services.phase3.reputation_su_service.requests.Session') as MockSession, \
         patch('app.services.phase3.reputation_su_service.time.sleep'):
        sess = MockSession.return_value
        if side_effect is not None:
            sess.get.side_effect = side_effect
        else:
            sess.get.return_value = _mock_get(html, status)
        ctx = (patch('app.services.phase3.reputation_su_service._deep_parse_records')
               if not deep_parse else _nullcontext())
        with ctx:
            cases, status_str = search_reputation_su(name)
    return cases, status_str, sess


class _nullcontext:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


# ── _is_blocked_page ──────────────────────────────────────────────────────

class TestBlockedPageDetection:

    def test_cloudflare_challenge_detected(self):
        assert _is_blocked_page(CLOUDFLARE_CHALLENGE) is True

    def test_ddos_guard_detected(self):
        assert _is_blocked_page(DDOS_GUARD_PAGE) is True

    def test_tiny_unknown_page_detected(self):
        assert _is_blocked_page(TINY_PAGE) is True

    def test_real_results_page_not_blocked(self):
        assert _is_blocked_page(REPUTATION_HTML) is False

    def test_large_empty_results_page_not_blocked(self):
        assert _is_blocked_page(EMPTY_RESULTS_HTML) is False

    def test_small_page_with_cards_not_blocked(self):
        # Cards present → it's a readable results page even if small
        small_with_card = '<div class="srch-card__affairs-box"><h3>1-1/2020</h3></div>'
        assert _is_blocked_page(small_with_card) is False

    def test_empty_string_not_blocked(self):
        assert _is_blocked_page('') is False


# ── search_reputation_su (mocked HTTP) ────────────────────────────────────

class TestSearchReputationSu:

    def test_returns_cases_and_ok_on_valid_html(self):
        cases, status, _ = _run_search(REPUTATION_HTML)
        assert len(cases) == 2
        assert status == 'ok'

    def test_empty_name_skipped(self):
        assert search_reputation_su('') == ([], 'skipped')
        assert search_reputation_su('   ') == ([], 'skipped')

    def test_non_200_http_error(self):
        cases, status, _ = _run_search('', status=503)
        assert (cases, status) == ([], 'http_error')

    def test_cloudflare_challenge_reports_blocked(self):
        """The core honesty fix: a bot-wall page must NOT read as clean."""
        cases, status, _ = _run_search(CLOUDFLARE_CHALLENGE)
        assert (cases, status) == ([], 'blocked')

    def test_tiny_page_reports_blocked(self):
        cases, status, _ = _run_search(TINY_PAGE)
        assert (cases, status) == ([], 'blocked')

    def test_genuinely_empty_page_reports_empty(self):
        cases, status, _ = _run_search(EMPTY_RESULTS_HTML)
        assert (cases, status) == ([], 'empty')

    def test_timeout_status(self):
        import requests as _req
        cases, status, _ = _run_search(side_effect=_req.Timeout('test'))
        assert (cases, status) == ([], 'timeout')

    def test_network_error_status(self):
        import requests as _req
        cases, status, _ = _run_search(side_effect=_req.RequestException('refused'))
        assert (cases, status) == ([], 'error')

    def test_uses_query_param_not_q(self):
        """Must use ?query= not ?q= — the latter returns unfiltered results."""
        _, _, sess = _run_search(REPUTATION_HTML, name='Петров Петр')
        url = sess.get.call_args_list[0].args[0]
        assert 'query=' in url
        assert '?q=' not in url

    def test_source_field_set(self):
        cases, _, _ = _run_search(REPUTATION_HTML)
        assert all(c['source'] == 'reputation.su' for c in cases)

    def test_session_closed_after_search(self):
        _, _, sess = _run_search(REPUTATION_HTML)
        sess.close.assert_called_once()

    def test_session_closed_even_on_error(self):
        import requests as _req
        _, _, sess = _run_search(side_effect=_req.Timeout('test'))
        sess.close.assert_called_once()

    def test_deep_parse_called_with_shared_session(self):
        with patch('app.services.phase3.reputation_su_service.requests.Session') as MockSession, \
             patch('app.services.phase3.reputation_su_service._deep_parse_records') as mock_dp:
            sess = MockSession.return_value
            sess.get.return_value = _mock_get(REPUTATION_HTML)
            search_reputation_su('Иванов Иван Иванович')
        mock_dp.assert_called_once()
        # Cookie continuity under Cloudflare: detail fetches reuse the session
        assert mock_dp.call_args.args[1] is sess

    def test_deep_parse_not_called_when_no_cases(self):
        with patch('app.services.phase3.reputation_su_service.requests.Session') as MockSession, \
             patch('app.services.phase3.reputation_su_service._deep_parse_records') as mock_dp:
            MockSession.return_value.get.return_value = _mock_get(EMPTY_RESULTS_HTML)
            search_reputation_su('Иванов Иван Иванович')
        mock_dp.assert_not_called()


# ── deep parse: budget, priority, abort ───────────────────────────────────

def _record(num, case_type='гражданское', url='https://reputation.su/sudrf/1'):
    return {
        'case_number': num,
        'case_type': case_type,
        'url': url,
        'criminal_articles': [],
        'verdict': '',
    }


class TestDeepParseBudget:

    def _run_deep(self, records, fetch_results, max_fetches=8):
        """fetch_results: list of strings returned per fetch, cycled."""
        calls = []

        def fake_fetch(url, session, timeout=10):
            calls.append(url)
            idx = len(calls) - 1
            if idx < len(fetch_results):
                return fetch_results[idx]
            return fetch_results[-1] if fetch_results else ''

        with patch('app.services.phase3.reputation_su_service._fetch_reputation_case_details',
                   side_effect=fake_fetch), \
             patch('app.services.phase3.reputation_su_service.time.sleep'):
            _deep_parse_records(records, session=MagicMock(), max_fetches=max_fetches)
        return calls

    def test_budget_caps_fetches(self):
        records = [_record(f'2-{i}/2020', url=f'https://reputation.su/sudrf/{i}')
                   for i in range(12)]
        calls = self._run_deep(records, ['some text'] * 12, max_fetches=8)
        assert len(calls) == 8

    def test_criminal_cases_fetched_first(self):
        records = [
            _record('2-1/2020', 'гражданское', 'https://reputation.su/sudrf/1'),
            _record('2-2/2020', 'гражданское', 'https://reputation.su/sudrf/2'),
            _record('1-9/2023', 'уголовное', 'https://reputation.su/sudrf/9'),
        ]
        calls = self._run_deep(records, ['text'] * 3, max_fetches=2)
        assert calls[0].endswith('/9')  # criminal first despite list order

    def test_admin_before_civil(self):
        records = [
            _record('2-1/2020', 'гражданское', 'https://reputation.su/sudrf/1'),
            _record('5-2/2021', 'административное', 'https://reputation.su/sudrf/2'),
        ]
        calls = self._run_deep(records, ['text'] * 2, max_fetches=1)
        assert calls[0].endswith('/2')

    def test_aborts_after_consecutive_failures(self):
        records = [_record(f'2-{i}/2020', url=f'https://reputation.su/sudrf/{i}')
                   for i in range(10)]
        calls = self._run_deep(records, [''] * 10)
        assert len(calls) == 3  # 3 consecutive failures → abort

    def test_success_resets_failure_counter(self):
        records = [_record(f'2-{i}/2020', url=f'https://reputation.su/sudrf/{i}')
                   for i in range(10)]
        # fail, fail, success, then nothing but failures → 3 more then abort
        calls = self._run_deep(records, ['', '', 'text', '', '', '', ''])
        assert len(calls) == 6

    def test_records_without_url_skipped(self):
        records = [_record('2-1/2020', url='')]
        calls = self._run_deep(records, ['text'])
        assert calls == []

    def test_already_enriched_skipped(self):
        rec = _record('1-1/2023', 'уголовное')
        rec['criminal_articles'] = ['ст. 158 УК РФ']
        calls = self._run_deep([rec], ['text'])
        assert calls == []

    def test_articles_and_verdict_extracted(self):
        rec = _record('1-1/2023', 'уголовное')
        detail = 'осуждён по ч.2 ст.228 УК РФ, назначено лишение свободы сроком на 3 года'
        with patch('app.services.phase3.reputation_su_service._fetch_reputation_case_details',
                   return_value=detail), \
             patch('app.services.phase3.reputation_su_service.time.sleep'):
            _deep_parse_records([rec], session=MagicMock())
        assert 'ч.2 ст.228 УК РФ' in rec['criminal_articles']
        assert rec['verdict'].startswith('лишение свободы')


class TestDetailFetch:

    def test_blocked_detail_page_returns_empty(self):
        sess = MagicMock()
        sess.get.return_value = _mock_get(CLOUDFLARE_CHALLENGE)
        assert _fetch_reputation_case_details('https://reputation.su/sudrf/1', sess) == ''

    def test_valid_detail_page_returns_text(self):
        sess = MagicMock()
        sess.get.return_value = _mock_get(
            '<html><body><div id="__nuxt">' + 'Дело № 1-1/2023 ' * 200 + '</div></body></html>'
        )
        text = _fetch_reputation_case_details('https://reputation.su/sudrf/1', sess)
        assert 'Дело' in text

    def test_http_error_returns_empty(self):
        sess = MagicMock()
        sess.get.return_value = _mock_get('', 404)
        assert _fetch_reputation_case_details('https://reputation.su/sudrf/1', sess) == ''

    def test_empty_url_no_request(self):
        sess = MagicMock()
        assert _fetch_reputation_case_details('', sess) == ''
        sess.get.assert_not_called()


# ── _parse_cards field extraction ─────────────────────────────────────────

class TestParseCardsFields:

    def test_criminal_case_type(self):
        cases = _parse_cards(REPUTATION_HTML, 'Иванов Иван Иванович')
        criminal = next((c for c in cases if c['case_number'] == '1-228/2023'), None)
        assert criminal is not None
        assert criminal['case_type'] == 'уголовное'

    def test_civil_case_type(self):
        cases = _parse_cards(REPUTATION_HTML, 'Иванов Иван Иванович')
        civil = next((c for c in cases if c['case_number'] == '2-500/2022'), None)
        assert civil is not None
        assert civil['case_type'] == 'гражданское'

    def test_defendant_role_detected(self):
        cases = _parse_cards(REPUTATION_HTML, 'Иванов Иван Иванович')
        criminal = next(c for c in cases if c['case_number'] == '1-228/2023')
        assert criminal['role'] == 'ответчик'

    def test_plaintiff_role_detected(self):
        cases = _parse_cards(REPUTATION_HTML, 'Иванов Иван Иванович')
        civil = next(c for c in cases if c['case_number'] == '2-500/2022')
        assert civil['role'] == 'истец'

    def test_subject_extracted(self):
        cases = _parse_cards(REPUTATION_HTML, 'Иванов Иван Иванович')
        criminal = next(c for c in cases if c['case_number'] == '1-228/2023')
        assert criminal['subject'] == 'Незаконный оборот наркотиков'

    def test_url_built_correctly(self):
        cases = _parse_cards(REPUTATION_HTML, 'Иванов Иван Иванович')
        criminal = next(c for c in cases if c['case_number'] == '1-228/2023')
        assert criminal['url'] == 'https://reputation.su/sudrf/99999'

    def test_date_extracted(self):
        cases = _parse_cards(REPUTATION_HTML, 'Иванов Иван Иванович')
        criminal = next(c for c in cases if c['case_number'] == '1-228/2023')
        assert criminal['date'] == '12.01.2023'

    def test_status_extracted(self):
        cases = _parse_cards(REPUTATION_HTML, 'Иванов Иван Иванович')
        criminal = next(c for c in cases if c['case_number'] == '1-228/2023')
        assert criminal['status'] == 'Рассмотрено'

    def test_deduplication_same_case_number(self):
        html = REPUTATION_HTML + '''
        <div class="srch-card__affairs-box">
          <h3>1-228/2023</h3>
          <ul><li><span>Категория</span><p>Уголовные</p></li></ul>
        </div>'''
        cases = _parse_cards(html, 'Иванов Иван')
        nums = [c['case_number'] for c in cases]
        assert nums.count('1-228/2023') == 1


# ── CourtCase conversion — no data loss ───────────────────────────────────

class TestCourtCaseConversionNoDataLoss:
    """Reputation.su records must survive the dict→CourtCase conversion in court_search."""

    def _run_conversion(self, rep_record):
        """Run the conversion path from court_search.search_by_name."""
        from app.services.phase3.court_search import CourtRecordSearch

        svc = CourtRecordSearch(timeout=5)
        with patch('app.services.phase3.reputation_su_service.search_reputation_su',
                   return_value=([rep_record], 'ok')), \
             patch('app.services.phase3.kad_arbitr_service.search_kad_arbitr_person',
                   return_value=([], 'empty')), \
             patch.object(svc, '_search_sudebnye_resheniya', return_value=[]), \
             patch('app.services.phase3.court_search.PLAYWRIGHT_AVAILABLE', False):
            results = svc.search_by_name('Иванов Иван Иванович')
        return results

    def test_criminal_articles_not_dropped(self):
        rec = {
            'case_number': '1-228/2023',
            'court_name': 'Суд',
            'case_type': 'уголовное',
            'date': '12.01.2023',
            'role': 'ответчик',
            'subject': 'Наркотики',
            'status': 'Рассмотрено',
            'url': 'https://reputation.su/sudrf/99999',
            'criminal_articles': ['ч.2 ст.228 УК РФ'],
            'verdict': 'условно 2 года',
            'source': 'reputation.su',
        }
        results = self._run_conversion(rec)
        assert len(results) == 1
        case = results[0]
        assert case.criminal_articles == ['ч.2 ст.228 УК РФ']

    def test_verdict_not_dropped(self):
        rec = {
            'case_number': '1-100/2023',
            'court_name': 'Суд',
            'case_type': 'уголовное',
            'date': '',
            'role': 'ответчик',
            'subject': '',
            'status': '',
            'url': 'https://reputation.su/sudrf/1',
            'criminal_articles': [],
            'verdict': 'штраф 50000 рублей',
            'source': 'reputation.su',
        }
        results = self._run_conversion(rec)
        assert results[0].verdict == 'штраф 50000 рублей'

    def test_subject_maps_to_category(self):
        rec = {
            'case_number': '2-200/2022',
            'court_name': 'Арбитражный суд',
            'case_type': 'гражданское',
            'date': '',
            'role': 'истец',
            'subject': 'Взыскание задолженности',
            'status': 'Рассмотрено',
            'url': '',
            'criminal_articles': [],
            'verdict': '',
            'source': 'reputation.su',
        }
        results = self._run_conversion(rec)
        assert results[0].category == 'Взыскание задолженности'

    def test_status_maps_to_result(self):
        rec = {
            'case_number': '3-300/2021',
            'court_name': 'Суд',
            'case_type': 'гражданское',
            'date': '',
            'role': 'участник',
            'subject': '',
            'status': 'В производстве',
            'url': '',
            'criminal_articles': [],
            'verdict': '',
            'source': 'reputation.su',
        }
        results = self._run_conversion(rec)
        assert results[0].result == 'В производстве'

    def test_empty_criminal_articles_stays_empty_list(self):
        rec = {
            'case_number': '4-400/2020',
            'court_name': 'Суд',
            'case_type': 'гражданское',
            'date': '',
            'role': 'истец',
            'subject': '',
            'status': '',
            'url': '',
            'source': 'reputation.su',
        }
        results = self._run_conversion(rec)
        assert results[0].criminal_articles == []

    def test_record_without_case_number_not_added(self):
        rec = {
            'case_number': '',
            'court_name': 'Суд',
            'case_type': '',
            'date': '',
            'role': '',
            'subject': '',
            'status': '',
            'url': '',
            'criminal_articles': [],
            'verdict': '',
            'source': 'reputation.su',
        }
        results = self._run_conversion(rec)
        assert results == []
