"""Tests for business record confidence display logic."""
import os
import pytest
from app.services.phase3.business_registry import BusinessRecord


def test_low_confidence_has_warning_status():
    """Low confidence record should have warning status and validation_warning."""
    r = BusinessRecord(
        company_name="ИП Иволгина Татьяна Владимировна",
        company_type="ИП",
        confidence="low",
        validation_warning="Фамилия кандидата 'зобов' не найдена в названии ИП",
        status="\u26a0\ufe0f Требует проверки (несоответствие имени)"
    )
    d = r.to_dict()
    assert d['confidence'] == 'low'
    assert '\u26a0' in d['status']
    assert d['validation_warning'] != ""


def test_template_renders_warning_for_low_confidence():
    """Dossier template should reference confidence and validation_warning."""
    template_path = os.path.join("app", "templates", "candidate_dossier.html")
    assert os.path.exists(template_path), f"Template not found: {template_path}"
    content = open(template_path, encoding='utf-8').read()
    assert "confidence" in content, "Template does not check confidence"
    assert "validation_warning" in content, "Template does not show validation_warning"


def test_high_confidence_no_warning():
    """High confidence record should not have a validation warning."""
    r = BusinessRecord(
        company_name="ИП Зобов Андрей Борисович",
        company_type="ИП",
        confidence="high",
        validation_warning=""
    )
    assert r.confidence == "high"
    assert r.validation_warning == ""
