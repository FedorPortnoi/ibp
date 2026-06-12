"""
Tests for local MVD/extremist DB honesty.

The committed data files are empty placeholders ([]). An empty DB must read
as "not loaded" (checked=False), never as a verified-clean screening against
the federal wanted / extremist lists — a high-stakes false clean.
"""

import json
from pathlib import Path

import pytest

from app.services.candidate.local_security_db import LocalSecurityDB
from app.services.candidate.sanctions_check import SanctionsService


def _write(dir_path: Path, name: str, payload):
    (dir_path / name).write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path


class TestHasDataRequiresRecords:

    def test_missing_file_is_false(self, data_dir):
        db = LocalSecurityDB(data_dir=str(data_dir))
        assert db.has_mvd_data() is False
        assert db.has_extremist_data() is False

    def test_empty_list_file_is_false(self, data_dir):
        """The exact production state: file exists but holds []."""
        _write(data_dir, 'mvd_wanted.json', [])
        _write(data_dir, 'extremist_list.json', [])
        db = LocalSecurityDB(data_dir=str(data_dir))
        assert db.has_mvd_data() is False
        assert db.has_extremist_data() is False

    def test_populated_file_is_true(self, data_dir):
        _write(data_dir, 'mvd_wanted.json', [{'full_name': 'Иванов Иван Иванович'}])
        _write(data_dir, 'extremist_list.json', [{'full_name': 'Петров Пётр'}])
        db = LocalSecurityDB(data_dir=str(data_dir))
        assert db.has_mvd_data() is True
        assert db.has_extremist_data() is True


class TestCheckMvdLocalHonesty:

    def _service_with_db(self, monkeypatch, db):
        svc = SanctionsService()
        import app.services.candidate.sanctions_check as sc
        monkeypatch.setattr(
            'app.services.candidate.local_security_db.LocalSecurityDB',
            lambda *a, **k: db,
        )
        return svc

    def test_empty_db_reports_unchecked(self, monkeypatch, data_dir):
        _write(data_dir, 'mvd_wanted.json', [])
        db = LocalSecurityDB(data_dir=str(data_dir))
        svc = self._service_with_db(monkeypatch, db)
        result = svc._check_mvd_local('Иванов Иван Иванович')
        assert result.checked is False
        assert result.found is False
        assert 'не загружена' in (result.error or '')

    def test_populated_db_no_match_is_verified_clean(self, monkeypatch, data_dir):
        _write(data_dir, 'mvd_wanted.json', [{'full_name': 'Сидоров Сидор Сидорович'}])
        db = LocalSecurityDB(data_dir=str(data_dir))
        svc = self._service_with_db(monkeypatch, db)
        result = svc._check_mvd_local('Иванов Иван Иванович')
        assert result.checked is True
        assert result.found is False

    def test_populated_db_match_is_found(self, monkeypatch, data_dir):
        _write(data_dir, 'mvd_wanted.json', [
            {'full_name': 'Иванов Иван Иванович', 'article': 'ст. 105 УК РФ'},
        ])
        db = LocalSecurityDB(data_dir=str(data_dir))
        svc = self._service_with_db(monkeypatch, db)
        result = svc._check_mvd_local('Иванов Иван Иванович')
        assert result.checked is True
        assert result.found is True


class TestCheckExtremistLocalHonesty:

    def _service_with_db(self, monkeypatch, db):
        monkeypatch.setattr(
            'app.services.candidate.local_security_db.LocalSecurityDB',
            lambda *a, **k: db,
        )
        return SanctionsService()

    def test_empty_db_reports_unchecked(self, monkeypatch, data_dir):
        _write(data_dir, 'extremist_list.json', [])
        db = LocalSecurityDB(data_dir=str(data_dir))
        svc = self._service_with_db(monkeypatch, db)
        result = svc._check_extremist_local('Иванов Иван Иванович')
        assert result.checked is False
        assert result.found is False
        assert 'не загружена' in (result.error or '')

    def test_populated_db_match_is_found(self, monkeypatch, data_dir):
        _write(data_dir, 'extremist_list.json', [
            {'full_name': 'Иванов Иван Иванович', 'reason': 'экстремизм'},
        ])
        db = LocalSecurityDB(data_dir=str(data_dir))
        svc = self._service_with_db(monkeypatch, db)
        result = svc._check_extremist_local('Иванов Иван Иванович')
        assert result.checked is True
        assert result.found is True
