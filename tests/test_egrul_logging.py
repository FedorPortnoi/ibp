"""Tests for EGRUL logging in search_by_inn."""
import logging
import pytest
from unittest.mock import patch
from app.services.phase3.business_registry import BusinessRegistrySearch, BusinessRecord


class TestEgrulLogging:
    """Tests for [EGRUL] log messages."""

    def setup_method(self):
        self.searcher = BusinessRegistrySearch()

    def test_egrul_logging_prefix(self, caplog):
        """search_by_inn should emit log messages with [EGRUL] prefix."""
        fake_record = BusinessRecord(
            company_name="ИП Зобов Андрей Борисович",
            company_type="ИП",
            inn="230804395297",
            confidence="high"
        )
        with patch.object(
            self.searcher, '_search_nalog_egrul', return_value=[fake_record]
        ):
            with caplog.at_level(logging.INFO):
                self.searcher.search_by_inn(
                    "230804395297", candidate_name="Зобов Андрей Борисович"
                )
        egrul_logs = [r for r in caplog.records if '[EGRUL]' in r.message]
        assert len(egrul_logs) > 0, "No logs with [EGRUL] prefix found"

    def test_invalid_record_logged_as_warning(self, caplog):
        """Invalid ИП record should produce a WARNING-level [EGRUL] log."""
        fake_record = BusinessRecord(
            company_name="ИП Иволгина Татьяна Владимировна",
            company_type="ИП",
            inn="230804395297",
            confidence="high"
        )
        with patch.object(
            self.searcher, '_search_nalog_egrul', return_value=[fake_record]
        ):
            with caplog.at_level(logging.WARNING):
                self.searcher.search_by_inn(
                    "230804395297", candidate_name="Зобов Андрей Борисович"
                )
        warning_logs = [
            r for r in caplog.records
            if r.levelno == logging.WARNING and 'EGRUL' in r.message
        ]
        assert len(warning_logs) > 0, "No WARNING log for invalid record found"

    def test_egrul_summary_log(self, caplog):
        """search_by_inn should emit a summary log with record count."""
        with patch.object(
            self.searcher, '_search_nalog_egrul', return_value=[]
        ):
            with caplog.at_level(logging.INFO):
                self.searcher.search_by_inn(
                    "230804395297", candidate_name="Зобов Андрей Борисович"
                )
        summary_logs = [
            r for r in caplog.records
            if 'Итого' in r.message and 'EGRUL' in r.message
        ]
        assert len(summary_logs) > 0, "No summary [EGRUL] log found"
