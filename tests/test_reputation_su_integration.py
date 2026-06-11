"""
Integration tests for reputation.su:
- search_reputation_su (mocked HTTP)
- CourtCase conversion in court_search (no data loss)
- Cloudflare challenge detection
"""

from unittest.mock import patch, MagicMock
import pytest

from app.services.phase3.reputation_su_service import (
    search_reputation_su,
    _parse_cards,
)


# ── HTML fixtures ─────────────────────────────────────────────────────────

CLOUDFLARE_CHALLENGE = '<html><head><title>Just a moment...</title></head><body>Click to continue</body></html>'

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


# ── search_reputation_su (mocked HTTP) ────────────────────────────────────

class TestSearchReputationSu:

    def test_returns_cases_on_valid_html(self):
        with patch('app.services.phase3.reputation_su_service.requests.get',
                   return_value=_mock_get(REPUTATION_HTML)), \
             patch('app.services.phase3.reputation_su_service._deep_parse_records'):
            results = search_reputation_su('Иванов Иван Иванович')
        assert len(results) == 2

    def test_empty_name_returns_empty(self):
        results = search_reputation_su('')
        assert results == []
        results2 = search_reputation_su('   ')
        assert results2 == []

    def test_non_200_returns_empty(self):
        with patch('app.services.phase3.reputation_su_service.requests.get',
                   return_value=_mock_get('', 503)):
            results = search_reputation_su('Иванов Иван')
        assert results == []

    def test_cloudflare_challenge_returns_empty(self):
        """Cloudflare 'Click to continue' page has no cards — returns []."""
        with patch('app.services.phase3.reputation_su_service.requests.get',
                   return_value=_mock_get(CLOUDFLARE_CHALLENGE)), \
             patch('app.services.phase3.reputation_su_service._deep_parse_records'):
            results = search_reputation_su('Иванов Иван')
        assert results == []

    def test_timeout_returns_empty(self):
        import requests as _req
        with patch('app.services.phase3.reputation_su_service.requests.get',
                   side_effect=_req.Timeout('test')):
            results = search_reputation_su('Иванов Иван')
        assert results == []

    def test_network_error_returns_empty(self):
        import requests as _req
        with patch('app.services.phase3.reputation_su_service.requests.get',
                   side_effect=_req.RequestException('connection refused')):
            results = search_reputation_su('Иванов Иван')
        assert results == []

    def test_uses_query_param_not_q(self):
        """Must use ?query= not ?q= — the latter returns unfiltered results."""
        captured = {}
        def fake_get(url, **kwargs):
            captured['url'] = url
            return _mock_get(REPUTATION_HTML)

        with patch('app.services.phase3.reputation_su_service.requests.get', fake_get), \
             patch('app.services.phase3.reputation_su_service._deep_parse_records'):
            search_reputation_su('Петров Петр')

        assert 'query=' in captured['url']
        assert '?q=' not in captured['url']

    def test_source_field_set_to_reputation_su(self):
        with patch('app.services.phase3.reputation_su_service.requests.get',
                   return_value=_mock_get(REPUTATION_HTML)), \
             patch('app.services.phase3.reputation_su_service._deep_parse_records'):
            results = search_reputation_su('Иванов Иван Иванович')
        assert all(r['source'] == 'reputation.su' for r in results)

    def test_deep_parse_called_when_cases_found(self):
        with patch('app.services.phase3.reputation_su_service.requests.get',
                   return_value=_mock_get(REPUTATION_HTML)), \
             patch('app.services.phase3.reputation_su_service._deep_parse_records') as mock_dp:
            search_reputation_su('Иванов Иван Иванович')
        mock_dp.assert_called_once()

    def test_deep_parse_not_called_when_no_cases(self):
        with patch('app.services.phase3.reputation_su_service.requests.get',
                   return_value=_mock_get(CLOUDFLARE_CHALLENGE)), \
             patch('app.services.phase3.reputation_su_service._deep_parse_records') as mock_dp:
            search_reputation_su('Иванов Иван Иванович')
        mock_dp.assert_not_called()


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
        from app.services.phase3.court_search import CourtRecordSearch, CourtCase
        import app.services.phase3.court_search as cm

        svc = CourtRecordSearch(timeout=5)
        with patch('app.services.phase3.reputation_su_service.search_reputation_su',
                   return_value=[rep_record]), \
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
