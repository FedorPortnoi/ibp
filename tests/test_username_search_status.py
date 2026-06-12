"""Username-search status honesty (sources #56 Snoop / #57 Maigret / #58 Sherlock).

These tools are DISCOVERY sources (username -> social accounts). When they are
not installed, the old code returned a bare [] which the dossier rendered as
"no accounts found" — a false clean. They now return (accounts, status), and
the trio is combined into one honest `username_search` source status so an
uninstalled toolset shows "search not performed" instead of "nothing found".

Also pins the Sherlock JSON parser fix: Sherlock emits a constructed url_user
for every site it probes, so `or bool(url)` marked every site a hit. The real
signal is the status field.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.candidate import social_analysis as sa
from app.services.sherlock_search import SherlockSearchService


# ── combine precedence ─────────────────────────────────────────────────────

class TestCombineUsernameStatus:

    def test_empty_input_returns_blank(self):
        assert sa._combine_username_status({}) == ''

    def test_all_unavailable(self):
        s = {'snoop': 'unavailable', 'maigret': 'unavailable', 'sherlock': 'unavailable'}
        assert sa._combine_username_status(s) == 'unavailable'

    def test_any_ok_wins(self):
        s = {'snoop': 'unavailable', 'maigret': 'ok', 'sherlock': 'error'}
        assert sa._combine_username_status(s) == 'ok'

    def test_empty_beats_error_and_unavailable(self):
        # At least one tool actually searched and was clean -> honest 'empty'.
        s = {'snoop': 'empty', 'maigret': 'unavailable', 'sherlock': 'error'}
        assert sa._combine_username_status(s) == 'empty'

    def test_error_beats_unavailable(self):
        s = {'snoop': 'error', 'maigret': 'unavailable'}
        assert sa._combine_username_status(s) == 'error'


# ── per-tool status: unavailable must not look like "searched, empty" ───────

def _svc(available: bool):
    inst = MagicMock()
    inst.available = available
    return MagicMock(return_value=inst)


class TestRunUnavailable:

    def test_snoop_unavailable(self):
        with patch('app.services.snoop_search.SnoopSearchService', _svc(False)):
            accts, status = sa._run_snoop_search(['ivanov'])
        assert (accts, status) == ([], 'unavailable')

    def test_maigret_unavailable(self):
        with patch('app.services.maigret_search.MaigretSearchService', _svc(False)):
            accts, status = sa._run_maigret_search(['ivanov'])
        assert (accts, status) == ([], 'unavailable')

    def test_sherlock_unavailable(self):
        with patch('app.services.sherlock_search.SherlockSearchService', _svc(False)):
            accts, status = sa._run_sherlock_search(['ivanov'])
        assert (accts, status) == ([], 'unavailable')

    def test_snoop_searched_empty(self):
        inst = MagicMock()
        inst.available = True
        inst.search_username.return_value = []
        inst.get_found_profiles.return_value = []
        with patch('app.services.snoop_search.SnoopSearchService', MagicMock(return_value=inst)):
            accts, status = sa._run_snoop_search(['ivanov'])
        assert (accts, status) == ([], 'empty')

    def test_snoop_found(self):
        inst = MagicMock()
        inst.available = True
        inst.search_username.return_value = ['raw']
        inst.get_found_profiles.return_value = [{'url': 'https://x/ivanov'}]
        with patch('app.services.snoop_search.SnoopSearchService', MagicMock(return_value=inst)):
            accts, status = sa._run_snoop_search(['ivanov'])
        assert status == 'ok' and len(accts) == 1


# ── Sherlock parser fix: url alone is not a hit ─────────────────────────────

class TestSherlockParser:

    def test_claimed_is_found(self, tmp_path):
        import json
        p = tmp_path / 'out.json'
        p.write_text(json.dumps({
            'GitHub': {'status': 'claimed', 'url_user': 'https://github.com/ivanov'},
        }), encoding='utf-8')
        rows = SherlockSearchService()._parse_json_output(p)
        assert rows and rows[0]['status'] == 'found'

    def test_url_without_claimed_status_is_not_found(self, tmp_path):
        # Sherlock emits url_user even for sites it did NOT confirm. Previously
        # `or bool(url)` made this a false positive.
        import json
        p = tmp_path / 'out.json'
        p.write_text(json.dumps({
            'SomeSite': {'status': 'available', 'url_user': 'https://somesite/ivanov'},
        }), encoding='utf-8')
        rows = SherlockSearchService()._parse_json_output(p)
        assert rows and rows[0]['status'] == 'not_found'
