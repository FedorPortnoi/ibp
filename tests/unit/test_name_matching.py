"""
Unit tests for Russian diminutive name matching.
Tests bidirectional lookup (formal ↔ diminutive).
"""

import pytest

from app.services.phase1.russian_diminutives import (
    get_diminutives,
    get_formal_name,
    get_all_name_variants,
    is_known_name,
)


class TestGetDiminutives:
    """Tests for formal → diminutive lookup."""

    def test_aleksandr_has_sasha(self):
        dims = get_diminutives("Александр")
        assert "Саша" in dims
        assert "Шура" in dims

    def test_case_insensitive(self):
        dims = get_diminutives("александр")
        assert "Саша" in dims

    def test_unknown_name_empty(self):
        dims = get_diminutives("Джон")
        assert dims == []

    def test_tikhon_diminutives(self):
        dims = get_diminutives("Тихон")
        assert "Тиша" in dims


class TestGetFormalName:
    """Tests for diminutive → formal reverse lookup."""

    def test_sasha_to_aleksandr(self):
        formals = get_formal_name("Саша")
        assert "Александр" in formals
        assert "Александра" in formals

    def test_shura_to_aleksandr(self):
        formals = get_formal_name("Шура")
        assert "Александр" in formals

    def test_unknown_diminutive(self):
        formals = get_formal_name("Незнакомка")
        assert formals == []

    def test_case_insensitive(self):
        formals = get_formal_name("саша")
        assert "Александр" in formals


class TestGetAllNameVariants:
    """Tests for bidirectional name variant expansion."""

    def test_formal_name_includes_self(self):
        variants = get_all_name_variants("Александр")
        assert variants[0] == "Александр"

    def test_formal_name_includes_diminutives(self):
        variants = get_all_name_variants("Александр")
        assert "Саша" in variants
        assert "Шура" in variants

    def test_diminutive_includes_formal(self):
        variants = get_all_name_variants("Саша")
        assert "Александр" in variants
        assert "Александра" in variants

    def test_diminutive_includes_all_sibling_diminutives(self):
        """Starting from Саша, we should also get Шура (sibling diminutive)."""
        variants = get_all_name_variants("Саша")
        assert "Шура" in variants

    def test_unknown_name_returns_self(self):
        variants = get_all_name_variants("Джон")
        assert variants == ["Джон"]

    def test_no_duplicates(self):
        variants = get_all_name_variants("Александр")
        lowered = [v.lower() for v in variants]
        assert len(lowered) == len(set(lowered))


class TestIsKnownName:
    """Tests for name dictionary membership."""

    def test_formal_name_known(self):
        assert is_known_name("Александр") is True

    def test_diminutive_known(self):
        assert is_known_name("Саша") is True

    def test_unknown_name(self):
        assert is_known_name("Джон") is False

    def test_case_insensitive(self):
        assert is_known_name("александр") is True
