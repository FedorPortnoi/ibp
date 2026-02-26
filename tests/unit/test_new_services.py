"""
Tests for new Phase 4-6 services.
- OpenSanctions service
- Local security database (MVD + Extremist)
- Checko.ru service
- Casebook.ru service
- Forgot-password oracle geo-restriction
- Maigret / Sherlock integration
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ================================================================
# OpenSanctions Service
# ================================================================

class TestOpenSanctionsService:
    """Test OpenSanctionsService."""

    def test_import(self):
        from app.services.candidate.opensanctions_service import OpenSanctionsService
        svc = OpenSanctionsService()
        assert svc.TIMEOUT == 20

    def test_match_result_to_dict(self):
        from app.services.candidate.opensanctions_service import OpenSanctionsMatch
        m = OpenSanctionsMatch(
            entity_id='abc123',
            name='Иванов Иван',
            score=0.85,
            datasets=['ru_fedsfm_terror'],
            countries=['RU'],
            match_details='Test match',
            url='https://opensanctions.org/entities/abc123/',
            source_name='Росфинмониторинг (терроризм)',
        )
        d = m.to_dict()
        assert d['entity_id'] == 'abc123'
        assert d['score'] == 0.85
        assert 'ru_fedsfm_terror' in d['datasets']

    def test_match_to_sanctions_dict(self):
        from app.services.candidate.opensanctions_service import OpenSanctionsMatch
        m = OpenSanctionsMatch(
            entity_id='abc123',
            name='Иванов',
            score=0.9,
            datasets=['ru_fedsfm_terror'],
            source_name='Росфинмониторинг (терроризм)',
        )
        d = m.to_sanctions_dict()
        assert d['source_name'] == 'Росфинмониторинг (терроризм)'
        assert d['checked'] is True
        assert d['found'] is True

    @patch('app.services.candidate.opensanctions_service.requests.Session')
    def test_check_person_no_match(self, mock_session_cls):
        from app.services.candidate.opensanctions_service import OpenSanctionsService

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'responses': {'q': {'results': []}},
        }
        mock_session.post.return_value = mock_resp

        svc = OpenSanctionsService()
        svc.session = mock_session
        matches = svc.check_person('Иванов Иван Иванович')
        assert matches == []

    @patch('app.services.candidate.opensanctions_service.requests.Session')
    def test_check_person_with_match(self, mock_session_cls):
        from app.services.candidate.opensanctions_service import OpenSanctionsService

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'responses': {'q': {'results': [
                {
                    'id': 'entity123',
                    'score': 0.92,
                    'properties': {
                        'name': ['Иванов Иван Иванович'],
                        'birthDate': ['1985-01-15'],
                        'country': ['RU'],
                    },
                    'datasets': ['ru_fedsfm_terror'],
                },
            ]}},
        }
        mock_session.post.return_value = mock_resp

        svc = OpenSanctionsService()
        svc.session = mock_session
        matches = svc.check_person('Иванов Иван Иванович')
        assert len(matches) == 1
        assert matches[0].score == 0.92
        assert 'ru_fedsfm_terror' in matches[0].datasets


# ================================================================
# Local Security Database
# ================================================================

class TestLocalSecurityDB:
    """Test LocalSecurityDB for MVD and extremist lookups."""

    def test_import(self):
        from app.services.candidate.local_security_db import LocalSecurityDB
        db = LocalSecurityDB()
        assert db is not None

    def test_empty_database(self):
        from app.services.candidate.local_security_db import LocalSecurityDB
        with tempfile.TemporaryDirectory() as tmpdir:
            db = LocalSecurityDB(data_dir=tmpdir)
            assert db.check_mvd_wanted('Иванов Иван') == []
            assert db.check_extremist_list('Иванов Иван') == []

    def test_mvd_match(self):
        from app.services.candidate.local_security_db import LocalSecurityDB
        with tempfile.TemporaryDirectory() as tmpdir:
            mvd_data = [
                {
                    'full_name': 'Иванов Иван Иванович',
                    'birth_date': '01.01.1985',
                    'article': 'ст. 159 УК РФ',
                    'category': 'federal',
                },
            ]
            with open(Path(tmpdir) / 'mvd_wanted.json', 'w', encoding='utf-8') as f:
                json.dump(mvd_data, f, ensure_ascii=False)

            db = LocalSecurityDB(data_dir=tmpdir)
            matches = db.check_mvd_wanted('Иванов Иван Иванович')
            assert len(matches) == 1
            assert matches[0].source == 'mvd_wanted'
            assert matches[0].full_name == 'Иванов Иван Иванович'

    def test_mvd_no_match(self):
        from app.services.candidate.local_security_db import LocalSecurityDB
        with tempfile.TemporaryDirectory() as tmpdir:
            mvd_data = [
                {'full_name': 'Петров Пётр Петрович'},
            ]
            with open(Path(tmpdir) / 'mvd_wanted.json', 'w', encoding='utf-8') as f:
                json.dump(mvd_data, f, ensure_ascii=False)

            db = LocalSecurityDB(data_dir=tmpdir)
            matches = db.check_mvd_wanted('Иванов Иван')
            assert matches == []

    def test_extremist_match(self):
        from app.services.candidate.local_security_db import LocalSecurityDB
        with tempfile.TemporaryDirectory() as tmpdir:
            ext_data = [
                {
                    'full_name': 'Сидоров Сидор',
                    'reason': 'Экстремизм',
                },
            ]
            with open(Path(tmpdir) / 'extremist_list.json', 'w', encoding='utf-8') as f:
                json.dump(ext_data, f, ensure_ascii=False)

            db = LocalSecurityDB(data_dir=tmpdir)
            matches = db.check_extremist_list('Сидоров Сидор')
            assert len(matches) == 1
            assert matches[0].source == 'extremist_list'

    def test_has_data_methods(self):
        from app.services.candidate.local_security_db import LocalSecurityDB
        with tempfile.TemporaryDirectory() as tmpdir:
            db = LocalSecurityDB(data_dir=tmpdir)
            assert db.has_mvd_data() is False
            assert db.has_extremist_data() is False

            # Create files
            with open(Path(tmpdir) / 'mvd_wanted.json', 'w') as f:
                json.dump([], f)
            with open(Path(tmpdir) / 'extremist_list.json', 'w') as f:
                json.dump([], f)

            db2 = LocalSecurityDB(data_dir=tmpdir)
            assert db2.has_mvd_data() is True
            assert db2.has_extremist_data() is True

    def test_to_sanctions_dict(self):
        from app.services.candidate.local_security_db import SecurityMatch
        m = SecurityMatch(
            source='mvd_wanted',
            full_name='Иванов Иван',
            details='Розыск',
        )
        d = m.to_sanctions_dict()
        assert d['source_name'] == 'МВД — розыск'
        assert d['checked'] is True
        assert d['found'] is True

    def test_name_matching_partial(self):
        """Test that last+first name match works without patronymic."""
        from app.services.candidate.local_security_db import LocalSecurityDB
        with tempfile.TemporaryDirectory() as tmpdir:
            data = [
                {'full_name': 'Иванов Иван Иванович'},
            ]
            with open(Path(tmpdir) / 'mvd_wanted.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)

            db = LocalSecurityDB(data_dir=tmpdir)
            # Match with just first+last
            matches = db.check_mvd_wanted('Иванов Иван')
            assert len(matches) == 1


# ================================================================
# Checko Service
# ================================================================

class TestCheckoService:
    """Test CheckoService."""

    def test_import(self):
        from app.services.phase3.checko_service import CheckoService
        svc = CheckoService()
        assert svc.TIMEOUT == 25

    def test_checko_record_to_fssp_dict(self):
        from app.services.phase3.checko_service import CheckoRecord
        r = CheckoRecord(
            record_type='enforcement',
            person_name='Иванов Иван',
            proceedings_number='12345/23/77001-ИП',
            amount=50000.0,
            is_active=True,
        )
        d = r.to_fssp_dict()
        assert d['debtor_name'] == 'Иванов Иван'
        assert d['proceedings_number'] == '12345/23/77001-ИП'
        assert d['source'] == 'checko.ru'

    @patch('app.services.phase3.checko_service.requests.Session')
    def test_search_enforcement_empty(self, mock_session_cls):
        from app.services.phase3.checko_service import CheckoService

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<html><body>Ничего не найдено</body></html>'
        mock_resp.apparent_encoding = 'utf-8'
        mock_session.get.return_value = mock_resp

        svc = CheckoService()
        svc.session = mock_session
        records = svc.search_enforcement('Тестовый Тест')
        assert records == []

    @patch('app.services.phase3.checko_service.requests.Session')
    def test_search_enforcement_403(self, mock_session_cls):
        from app.services.phase3.checko_service import CheckoService

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_session.get.return_value = mock_resp

        svc = CheckoService()
        svc.session = mock_session
        records = svc.search_enforcement('Тестовый Тест')
        assert records == []


# ================================================================
# Casebook Service
# ================================================================

class TestCasebookService:
    """Test CasebookService."""

    def test_import(self):
        from app.services.phase3.casebook_service import CasebookService
        svc = CasebookService()
        assert svc.TIMEOUT == 25

    def test_casebook_record_to_court_dict(self):
        from app.services.phase3.casebook_service import CasebookRecord
        r = CasebookRecord(
            case_number='А40-12345/2023',
            court_name='Арбитражный суд г. Москвы',
            date='15.06.2023',
        )
        d = r.to_court_dict()
        assert d['case_number'] == 'А40-12345/2023'
        assert d['source'] == 'casebook.ru'
        assert d['case_type'] == 'Арбитражное дело'


# ================================================================
# Forgot-Password Oracle Geo-Restriction
# ================================================================

class TestForgotPasswordGeoRestriction:
    """Test that geo-restricted checkers are properly filtered."""

    def test_gosuslugi_marked_geo_restricted(self):
        from app.services.phase2.forgot_password_oracle import GosuslugiChecker
        assert GosuslugiChecker.GEO_RESTRICTED is True

    def test_sberbank_marked_geo_restricted(self):
        from app.services.phase2.forgot_password_oracle import SberbankChecker
        assert SberbankChecker.GEO_RESTRICTED is True

    def test_vk_not_geo_restricted(self):
        from app.services.phase2.forgot_password_oracle import VKChecker
        assert VKChecker.GEO_RESTRICTED is False

    def test_oracle_skips_geo_restricted_by_default(self):
        """Without env var, Gosuslugi and Sberbank should be skipped."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove the env var if set
            os.environ.pop('ENABLE_GEO_RESTRICTED_CHECKERS', None)
            from app.services.phase2.forgot_password_oracle import ForgotPasswordOracle
            oracle = ForgotPasswordOracle()
            names = [c.SERVICE_NAME for c in oracle.checkers]
            assert 'gosuslugi' not in names
            assert 'sberbank' not in names
            # Global checkers should still be present
            assert 'vk' in names
            assert 'mailru' in names

    def test_oracle_includes_geo_restricted_when_enabled(self):
        """With ENABLE_GEO_RESTRICTED_CHECKERS=1, all checkers should be present."""
        with patch.dict(os.environ, {'ENABLE_GEO_RESTRICTED_CHECKERS': '1'}):
            from app.services.phase2.forgot_password_oracle import ForgotPasswordOracle
            oracle = ForgotPasswordOracle()
            names = [c.SERVICE_NAME for c in oracle.checkers]
            assert 'gosuslugi' in names
            assert 'sberbank' in names


# ================================================================
# Sanctions Service with New Sources
# ================================================================

class TestSanctionsServiceIntegration:
    """Test that the updated SanctionsService uses new sources."""

    def test_import(self):
        from app.services.candidate.sanctions_check import SanctionsService
        svc = SanctionsService()
        assert svc is not None

    def test_check_all_returns_results(self):
        """check_all should return a list even when sources fail."""
        from app.services.candidate.sanctions_check import SanctionsService

        with patch.object(SanctionsService, '_check_opensanctions', return_value=[]):
            with patch.object(SanctionsService, '_check_mvd_local', return_value=MagicMock(
                source_name='МВД — розыск', checked=True, found=False,
            )):
                with patch.object(SanctionsService, '_check_extremist_local', return_value=MagicMock(
                    source_name='Перечень экстремистов', checked=True, found=False,
                )):
                    with patch.object(SanctionsService, '_check_interpol', return_value=MagicMock(
                        source_name='Интерпол', checked=True, found=False,
                    )):
                        with patch.object(SanctionsService, '_check_rosfinmonitoring', return_value=MagicMock(
                            source_name='Росфинмониторинг', checked=False, found=False,
                        )):
                            with patch.object(SanctionsService, '_check_mvd_wanted', return_value=MagicMock(
                                source_name='МВД — розыск (live)', checked=False, found=False,
                            )):
                                svc = SanctionsService()
                                results = svc.check_all('Тестовый Тест')
                                assert len(results) >= 4


# ================================================================
# Maigret / Sherlock Services
# ================================================================

class TestMaigretService:
    """Test MaigretSearchService."""

    def test_import(self):
        from app.services.maigret_search import MaigretSearchService
        svc = MaigretSearchService()
        assert svc is not None

    def test_unavailable_returns_empty(self):
        from app.services.maigret_search import MaigretSearchService
        svc = MaigretSearchService()
        svc._available = False
        results = svc.search_username('test')
        assert results == []

    def test_parse_json_output(self):
        from app.services.maigret_search import MaigretSearchService
        svc = MaigretSearchService()
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8',
        ) as f:
            json.dump({
                'VK': {'url_user': 'https://vk.com/test', 'status': 'Claimed'},
                'GitHub': {'url_user': 'https://github.com/test', 'status': 'Available'},
            }, f)
            f.flush()
            results = svc._parse_json_output(Path(f.name))
        os.unlink(f.name)
        found = [r for r in results if r['status'] == 'found']
        assert len(found) == 1
        assert found[0]['platform'] == 'VK'


class TestSherlockService:
    """Test SherlockSearchService."""

    def test_import(self):
        from app.services.sherlock_search import SherlockSearchService
        svc = SherlockSearchService()
        assert svc is not None

    def test_unavailable_returns_empty(self):
        from app.services.sherlock_search import SherlockSearchService
        svc = SherlockSearchService()
        svc._available = False
        results = svc.search_username('test')
        assert results == []

    def test_get_found_profiles(self):
        from app.services.sherlock_search import SherlockSearchService
        svc = SherlockSearchService()
        results = [
            {'platform': 'VK', 'url': 'https://vk.com/test', 'status': 'found'},
            {'platform': 'GitHub', 'url': 'https://github.com/test', 'status': 'not_found'},
        ]
        found = svc.get_found_profiles(results)
        assert len(found) == 1
        assert found[0]['platform'] == 'VK'
