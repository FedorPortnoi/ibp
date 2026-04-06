"""Tests for BusinessRecord owner validation."""
import pytest
from unittest.mock import patch
from app.services.phase3.business_registry import BusinessRegistrySearch, BusinessRecord


class TestValidateBusinessRecordOwner:
    """Tests for _validate_business_record_owner."""

    def setup_method(self):
        self.searcher = BusinessRegistrySearch()

    def test_ip_wrong_surname_is_invalid(self):
        """ИП with a different surname should be flagged as invalid."""
        record = BusinessRecord(
            company_name="ИП Иволгина Татьяна Владимировна",
            company_type="ИП",
            inn="230804395297",
            confidence="high"
        )
        is_valid, reason = self.searcher._validate_business_record_owner(
            record, "Зобов Андрей Борисович"
        )
        assert is_valid is False
        assert "зобов" in reason.lower() or "иволгина" in reason.lower()

    def test_ip_correct_surname_is_valid(self):
        """ИП with matching surname should be valid."""
        record = BusinessRecord(
            company_name="ИП Зобов Андрей Борисович",
            company_type="ИП",
            inn="230804395297",
            confidence="high"
        )
        is_valid, reason = self.searcher._validate_business_record_owner(
            record, "Зобов Андрей Борисович"
        )
        assert is_valid is True

    def test_ooo_always_valid(self):
        """ООО should always pass validation (can't check by surname)."""
        record = BusinessRecord(
            company_name="ООО Ромашка",
            company_type="ООО",
            inn="1234567890",
            confidence="high"
        )
        is_valid, _ = self.searcher._validate_business_record_owner(
            record, "Зобов Андрей Борисович"
        )
        assert is_valid is True

    def test_search_by_inn_marks_invalid_record(self):
        """search_by_inn should set low confidence and warning for invalid ИП."""
        fake_record = BusinessRecord(
            company_name="ИП Иволгина Татьяна Владимировна",
            company_type="ИП",
            inn="230804395297",
            confidence="high"
        )
        with patch.object(
            self.searcher, '_search_nalog_egrul', return_value=[fake_record]
        ):
            results = self.searcher.search_by_inn(
                "230804395297", candidate_name="Зобов Андрей Борисович"
            )
        assert len(results) == 1
        assert results[0].confidence == "low"
        assert results[0].validation_warning != ""
        assert "Требует проверки" in results[0].status

    def test_business_record_has_validation_warning(self):
        """BusinessRecord should have validation_warning field in to_dict()."""
        r = BusinessRecord(company_name="Тест", company_type="ИП")
        assert hasattr(r, 'validation_warning')
        assert r.validation_warning == ""
        assert 'validation_warning' in r.to_dict()
