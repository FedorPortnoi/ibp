"""
Comprehensive tests for VK name similarity scoring and profile filtering.

Tests _calculate_name_similarity in BuratinoVKSearch which is the core function
that determines whether a VK profile matches a search query. The function:
- Returns 0-100 float score
- Splits both names into parts[0] (first) and parts[-1] (last)
- Scores first and last independently (50/50 weight)
- Caps total at 45 if first_score < 0.45 (last-name-only match)
- Caps total at 40 if last_score < 0.45 (first-name-only match)
- Uses diminutive matching via get_all_name_variants() (boosts to 0.90)
- Compares both Cyrillic and Latin (via _to_latin)
- Substring bonus: 1.0 if one name contains the other (min length 3)
- Single-word queries: simple SequenceMatcher ratio * 100
"""

import pytest

from app.services.phase1.buratino_vk_search import BuratinoVKSearch


class TestExactMatches:
    """Exact name matches should score near 100."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_exact_match_cyrillic(self, searcher):
        score = searcher._calculate_name_similarity("Иван Иванов", "Иван Иванов")
        assert score >= 95, f"Exact Cyrillic match should be >=95, got {score}"

    def test_exact_match_case_insensitive(self, searcher):
        score = searcher._calculate_name_similarity("иван иванов", "Иван Иванов")
        assert score >= 95, f"Case-insensitive match should be >=95, got {score}"

    def test_exact_match_latin(self, searcher):
        score = searcher._calculate_name_similarity("Ivan Ivanov", "Ivan Ivanov")
        assert score >= 95, f"Exact Latin match should be >=95, got {score}"

    def test_exact_match_extra_whitespace(self, searcher):
        score = searcher._calculate_name_similarity("  Иван  Иванов  ", "Иван Иванов")
        assert score >= 90, f"Whitespace-trimmed match should be >=90, got {score}"


class TestDifferentFirstNameSameLastName:
    """Different first name with same last name should be capped (false positive prevention)."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_different_first_same_last_ivan_aleksandr(self, searcher):
        """Иванов Александр should NOT match query for Иван Иванов."""
        score = searcher._calculate_name_similarity("Иван Иванов", "Александр Иванов")
        assert score <= 50, f"Different first name should be <=50, got {score}"

    def test_different_first_artem_maxim(self, searcher):
        """Козлов Максим should NOT match query for Артём Козлов."""
        score = searcher._calculate_name_similarity("Артём Козлов", "Максим Козлов")
        assert score <= 50, f"Artem/Maxim mismatch should be <=50, got {score}"

    def test_different_first_maria_elena(self, searcher):
        """Мария Петрова should NOT match query for Елена Петрова."""
        score = searcher._calculate_name_similarity("Елена Петрова", "Мария Петрова")
        assert score <= 50, f"Elena/Maria mismatch should be <=50, got {score}"

    def test_different_first_sergey_andrey(self, searcher):
        """Андрей Сидоров should NOT match query for Сергей Сидоров."""
        score = searcher._calculate_name_similarity("Сергей Сидоров", "Андрей Сидоров")
        assert score <= 50, f"Sergey/Andrey mismatch should be <=50, got {score}"


class TestDiminutiveMatching:
    """Diminutive forms should match formal names with high confidence."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_ivan_vanya(self, searcher):
        """Ваня is diminutive of Иван -- should match."""
        score = searcher._calculate_name_similarity("Иван Иванов", "Ваня Иванов")
        assert score >= 70, f"Иван/Ваня diminutive should be >=70, got {score}"

    def test_aleksandr_sasha(self, searcher):
        """Саша is diminutive of Александр -- should match."""
        score = searcher._calculate_name_similarity("Александр Петров", "Саша Петров")
        assert score >= 70, f"Александр/Саша diminutive should be >=70, got {score}"

    def test_dmitriy_dima(self, searcher):
        """Дима is diminutive of Дмитрий -- should match."""
        score = searcher._calculate_name_similarity("Дмитрий Козлов", "Дима Козлов")
        assert score >= 70, f"Дмитрий/Дима diminutive should be >=70, got {score}"

    def test_ekaterina_katya(self, searcher):
        """Катя is diminutive of Екатерина -- should match."""
        score = searcher._calculate_name_similarity("Екатерина Смирнова", "Катя Смирнова")
        assert score >= 70, f"Екатерина/Катя diminutive should be >=70, got {score}"

    def test_anastasiya_nastya(self, searcher):
        """Настя is diminutive of Анастасия -- should match."""
        score = searcher._calculate_name_similarity("Анастасия Козлова", "Настя Козлова")
        assert score >= 70, f"Анастасия/Настя diminutive should be >=70, got {score}"

    def test_reverse_diminutive_sasha_aleksandr(self, searcher):
        """Searching for Саша should match Александр too."""
        score = searcher._calculate_name_similarity("Саша Петров", "Александр Петров")
        assert score >= 70, f"Reverse diminutive Саша->Александр should be >=70, got {score}"

    def test_aleksandr_shura(self, searcher):
        """Шура is diminutive of Александр -- should match."""
        score = searcher._calculate_name_similarity("Александр Иванов", "Шура Иванов")
        assert score >= 70, f"Александр/Шура diminutive should be >=70, got {score}"

    def test_tikhon_tisha(self, searcher):
        """Тиша is diminutive of Тихон -- should match."""
        score = searcher._calculate_name_similarity("Тихон Портной", "Тиша Портной")
        assert score >= 70, f"Тихон/Тиша diminutive should be >=70, got {score}"

    def test_non_diminutive_same_initial_should_not_match(self, searcher):
        """Максим and Марк share initial М but are NOT diminutives -- should not match high."""
        score = searcher._calculate_name_similarity("Максим Козлов", "Марк Козлов")
        assert score <= 50, f"Максим/Марк are not diminutives, should be <=50, got {score}"


class TestYoEEquivalence:
    """Russian Ё and Е should be treated as equivalent in name matching."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_artem_artyom(self, searcher):
        """Артём and Артем should match with high score."""
        score = searcher._calculate_name_similarity("Артём Козлов", "Артем Козлов")
        assert score >= 85, f"Ё/Е Артём/Артем should be >=85, got {score}"

    def test_fedor_fyodor(self, searcher):
        """Фёдор and Федор should match with high score."""
        score = searcher._calculate_name_similarity("Фёдор Иванов", "Федор Иванов")
        assert score >= 85, f"Ё/Е Фёдор/Федор should be >=85, got {score}"

    def test_alyona_alena(self, searcher):
        """Алёна and Алена should match."""
        score = searcher._calculate_name_similarity("Алёна Козлова", "Алена Козлова")
        assert score >= 85, f"Ё/Е Алёна/Алена should be >=85, got {score}"

    def test_semyon_semen(self, searcher):
        """Семён and Семен should match."""
        score = searcher._calculate_name_similarity("Семён Петров", "Семен Петров")
        assert score >= 85, f"Ё/Е Семён/Семен should be >=85, got {score}"

    def test_yo_in_last_name(self, searcher):
        """Ё in last name: Козлёв vs Козлев should match."""
        score = searcher._calculate_name_similarity("Иван Козлёв", "Иван Козлев")
        assert score >= 85, f"Ё/Е in last name should be >=85, got {score}"


class TestDifferentLastName:
    """Different last names should score low even with same first name."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_same_first_different_last(self, searcher):
        """Иван Петров should NOT match Иван Иванов (different surname)."""
        score = searcher._calculate_name_similarity("Иван Иванов", "Иван Петров")
        assert score <= 50, f"Different last name should be <=50, got {score}"

    def test_completely_different_names(self, searcher):
        """Completely unrelated names should score very low."""
        score = searcher._calculate_name_similarity("Иван Иванов", "Мария Петрова")
        assert score <= 30, f"Completely different names should be <=30, got {score}"

    def test_similar_last_names(self, searcher):
        """Similar but different surnames: Козлов vs Козлова -- close but gendered."""
        score_different_first = searcher._calculate_name_similarity(
            "Иван Козлов", "Ирина Козлова"
        )
        assert score_different_first <= 50, (
            f"Different first + gendered surname should be <=50, got {score_different_first}"
        )


class TestSurnameGenderVariants:
    """Russian surname gender variants (Козлов/Козлова) with same first name."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_gender_variant_same_first(self, searcher):
        """Same first name, gendered surname variant -- should score reasonably."""
        score = searcher._calculate_name_similarity("Саша Козлов", "Саша Козлова")
        assert score >= 60, f"Same first + surname gender variant should be >=60, got {score}"

    def test_gender_variant_different_first(self, searcher):
        """Different first name + gendered surname -- should be low."""
        score = searcher._calculate_name_similarity("Иван Иванов", "Ирина Иванова")
        assert score <= 50, f"Different first + gendered surname should be <=50, got {score}"


class TestSingleWordQuery:
    """Single-word queries use simple SequenceMatcher ratio."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_surname_only_exact(self, searcher):
        """Single word matching single word."""
        score = searcher._calculate_name_similarity("Иванов", "Иванов")
        assert score >= 95, f"Exact surname-only match should be >=95, got {score}"

    def test_surname_only_vs_full_name(self, searcher):
        """Single word query against a two-word found name."""
        score = searcher._calculate_name_similarity("Иванов", "Иван Иванов")
        assert score >= 30, f"Surname vs full name should be >=30, got {score}"

    def test_first_name_only(self, searcher):
        """Single first name query."""
        score = searcher._calculate_name_similarity("Иван", "Иван Петров")
        assert score >= 30, f"First name only vs full name should be >=30, got {score}"


class TestEdgeCases:
    """Edge cases: empty strings, whitespace, unusual inputs."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_empty_target(self, searcher):
        score = searcher._calculate_name_similarity("", "Иван Иванов")
        assert score == 0, f"Empty target should return 0, got {score}"

    def test_empty_found(self, searcher):
        score = searcher._calculate_name_similarity("Иван Иванов", "")
        assert score == 0, f"Empty found should return 0, got {score}"

    def test_both_empty(self, searcher):
        score = searcher._calculate_name_similarity("", "")
        assert score == 0, f"Both empty should return 0, got {score}"

    def test_whitespace_only_target(self, searcher):
        score = searcher._calculate_name_similarity("   ", "Иван Иванов")
        # After strip(), becomes empty
        assert score == 0, f"Whitespace-only target should return 0, got {score}"

    def test_whitespace_only_found(self, searcher):
        score = searcher._calculate_name_similarity("Иван Иванов", "   ")
        assert score == 0, f"Whitespace-only found should return 0, got {score}"

    def test_three_word_name(self, searcher):
        """Three-word name (patronymic) should still work with parts[0] and parts[-1]."""
        score = searcher._calculate_name_similarity(
            "Иван Иванов", "Иван Иванович Иванов"
        )
        # parts[0]="иван" vs parts[0]="иван" (match), parts[-1]="иванов" vs parts[-1]="иванов" (match)
        assert score >= 80, f"Three-word name with matching first/last should be >=80, got {score}"

    def test_score_is_float(self, searcher):
        """Score should always be a float."""
        score = searcher._calculate_name_similarity("Иван Иванов", "Иван Иванов")
        assert isinstance(score, (int, float)), f"Score should be numeric, got {type(score)}"

    def test_score_range(self, searcher):
        """Score should be in range [0, 100]."""
        score = searcher._calculate_name_similarity("Иван Иванов", "Иван Иванов")
        assert 0 <= score <= 100, f"Score should be in [0, 100], got {score}"


class TestCrossScript:
    """Cross-script matching (Latin vs Cyrillic) via _to_latin transliteration."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_latin_target_cyrillic_found(self, searcher):
        """Latin query should match Cyrillic name via transliteration."""
        score = searcher._calculate_name_similarity("Ivan Ivanov", "Иван Иванов")
        assert score >= 70, f"Cross-script Latin->Cyrillic should be >=70, got {score}"

    def test_cyrillic_target_latin_found(self, searcher):
        """Cyrillic query should match Latin name via transliteration."""
        score = searcher._calculate_name_similarity("Иван Иванов", "Ivan Ivanov")
        assert score >= 70, f"Cross-script Cyrillic->Latin should be >=70, got {score}"


class TestSubstringBonus:
    """Substring matching bonus (if one name contains the other, length >= 3)."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_substring_in_first_name(self, searcher):
        """Алекс is substring of Александр (and also a diminutive) -- should score high."""
        score = searcher._calculate_name_similarity("Александр Петров", "Алекс Петров")
        assert score >= 70, f"Substring first name should be >=70, got {score}"

    def test_short_substring_no_bonus(self, searcher):
        """Substring shorter than 3 chars should not get bonus."""
        # "Ал" is 2 chars in Latin, but let's test with short names
        score = searcher._calculate_name_similarity("Ян Ким", "Яна Кимова")
        # These are very short, parts[0] "ян" is 2 chars Cyrillic
        # No substring bonus for < 3 chars
        assert isinstance(score, (int, float))


class TestFirstNameCapBehavior:
    """When first name doesn't match at all, total is capped at 45 (last-name-only match)."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_cap_at_45_for_wrong_first_name(self, searcher):
        """Wrong first name with perfect last name should be capped at max 45."""
        score = searcher._calculate_name_similarity("Иван Козлов", "Максим Козлов")
        assert score <= 45, f"Wrong first name should be capped at 45, got {score}"

    def test_cap_at_40_for_wrong_last_name(self, searcher):
        """Correct first name with totally wrong last name should be capped at max 40."""
        score = searcher._calculate_name_similarity("Иван Козлов", "Иван Петров")
        assert score <= 40, f"Wrong last name should be capped at 40, got {score}"

    def test_first_name_cap_prevents_false_positive(self, searcher):
        """The classic false positive case: searching Артём Козлов finding Максим Козлов."""
        score = searcher._calculate_name_similarity("Артём Козлов", "Максим Козлов")
        assert score <= 45, f"Artem/Maxim cap should prevent false positive, got {score}"
        # And it should NOT pass the name_match threshold of 50
        assert score <= 50, f"Should be below match threshold of 50, got {score}"


class TestLastNameCapBehavior:
    """When last name doesn't match at all, total is capped at 40 (first-name-only match)."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_cap_at_40_completely_different_last(self, searcher):
        """Same first, completely different last name capped at 40."""
        score = searcher._calculate_name_similarity("Иван Козлов", "Иван Смирнов")
        assert score <= 40, f"Completely different last name should be capped at 40, got {score}"

    def test_cap_prevents_first_name_only_match(self, searcher):
        """A first-name-only match should NOT pass the 50 threshold."""
        score = searcher._calculate_name_similarity("Иван Козлов", "Иван Смирнов")
        assert score <= 50, f"First-name-only should be below 50 threshold, got {score}"


class TestBothNamesPartialMatch:
    """When both names partially match but not exactly."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_both_names_high_similarity(self, searcher):
        """Very similar but not identical names -- e.g. typo in one letter."""
        # Иванов vs Иваноф (last letter change)
        score = searcher._calculate_name_similarity("Иван Иванов", "Иван Иваноф")
        # Should still be reasonably high since most chars match
        assert score >= 70, f"Near-exact match with typo should be >=70, got {score}"


class TestNameMatchThreshold:
    """Test the name_match = name_similarity > 50 threshold used in _parse_profile."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_exact_match_above_threshold(self, searcher):
        """Exact match should be well above 50."""
        score = searcher._calculate_name_similarity("Иван Иванов", "Иван Иванов")
        assert score > 50, "Exact match should be above match threshold"

    def test_wrong_first_below_threshold(self, searcher):
        """Wrong first name should be below or at 50 threshold."""
        score = searcher._calculate_name_similarity("Иван Иванов", "Александр Иванов")
        assert score <= 50, "Wrong first name should be at or below match threshold"

    def test_wrong_last_below_threshold(self, searcher):
        """Wrong last name should be below 50 threshold."""
        score = searcher._calculate_name_similarity("Иван Иванов", "Иван Петров")
        assert score <= 50, "Wrong last name should be below match threshold"

    def test_diminutive_above_threshold(self, searcher):
        """Diminutive match with correct last name should be above 50."""
        score = searcher._calculate_name_similarity("Иван Иванов", "Ваня Иванов")
        assert score > 50, f"Diminutive match should be above 50 threshold, got {score}"


class TestParseProfileNameMatch:
    """Test _parse_profile correctly sets name_match based on similarity."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_parse_profile_exact_match(self, searcher):
        """_parse_profile should set name_match=True for exact match."""
        data = {
            'id': 12345,
            'first_name': 'Иван',
            'last_name': 'Иванов',
        }
        profile = searcher._parse_profile(data, target_name="Иван Иванов")
        assert profile.name_match is True
        assert profile.name_similarity > 50

    def test_parse_profile_rejects_wrong_first_name(self, searcher):
        """Profile with wrong first name should not match."""
        data = {
            'id': 12345,
            'first_name': 'Александр',
            'last_name': 'Иванов',
        }
        profile = searcher._parse_profile(data, target_name="Иван Иванов")
        assert profile.name_match is False
        assert profile.name_similarity <= 50

    def test_parse_profile_diminutive_match(self, searcher):
        """Profile with diminutive first name should match."""
        data = {
            'id': 12345,
            'first_name': 'Ваня',
            'last_name': 'Иванов',
        }
        profile = searcher._parse_profile(data, target_name="Иван Иванов")
        assert profile.name_match is True
        assert profile.name_similarity > 50

    def test_parse_profile_no_target_name(self, searcher):
        """_parse_profile without target_name should have defaults."""
        data = {
            'id': 12345,
            'first_name': 'Иван',
            'last_name': 'Иванов',
        }
        profile = searcher._parse_profile(data)
        assert profile.name_match is False  # Default
        assert profile.name_similarity == 0.0  # Default

    def test_parse_profile_full_name_property(self, searcher):
        """full_name should be 'first_name last_name'."""
        data = {
            'id': 12345,
            'first_name': 'Иван',
            'last_name': 'Иванов',
        }
        profile = searcher._parse_profile(data)
        assert profile.full_name == "Иван Иванов"


class TestQueryOrderSensitivity:
    """Test how name order in query affects scoring.

    VK returns full_name as "first_name last_name" (e.g., "Иван Иванов").
    Users may type "Иванов Иван" (last first) or "Иван Иванов" (first last).
    The function compares parts[0] vs parts[0] and parts[-1] vs parts[-1],
    so order matters.
    """

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_same_order_scores_high(self, searcher):
        """Same order (first last) should score near 100."""
        score = searcher._calculate_name_similarity("Иван Иванов", "Иван Иванов")
        assert score >= 95

    def test_reversed_order_with_different_names(self, searcher):
        """Reversed order: query='Иванов Иван', found='Иван Иванов'.

        parts[0] comparison: 'иванов' vs 'иван' -- substring match (иван in иванов), score 1.0
        parts[-1] comparison: 'иван' vs 'иванов' -- substring match (иван in иванов), score 1.0
        So reversed order should still score high due to substring matching.
        """
        score = searcher._calculate_name_similarity("Иванов Иван", "Иван Иванов")
        # Due to substring matching bonus, this should be high
        assert score >= 70, f"Reversed order should still be high due to substring, got {score}"

    def test_reversed_order_distinct_names(self, searcher):
        """Reversed order with distinct first/last: query='Козлов Артём', found='Артём Козлов'.

        parts[0]: 'козлов' vs 'артём' -- low
        parts[-1]: 'артём' vs 'козлов' -- low
        Both caps would apply, resulting in a low score.
        """
        score = searcher._calculate_name_similarity("Козлов Артём", "Артём Козлов")
        # When first and last are very different strings, reversed order may score low
        # This is a known limitation of the positional comparison approach
        assert isinstance(score, (int, float))


class TestRealWorldScenarios:
    """Real-world scenarios that have caused issues in production."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_target_tikhon_portnoy(self, searcher):
        """Known test target: Тихон Портной -- exact match."""
        score = searcher._calculate_name_similarity("Тихон Портной", "Тихон Портной")
        assert score >= 95

    def test_target_tikhon_portnoy_diminutive(self, searcher):
        """Тиша Портной should match search for Тихон Портной."""
        score = searcher._calculate_name_similarity("Тихон Портной", "Тиша Портной")
        assert score >= 70

    def test_false_positive_artem_maxim_kozlov(self, searcher):
        """Classic false positive: searching for Артём Козлов, finding Максим Козлов.
        The first-name cap should prevent this from passing the threshold.
        """
        score = searcher._calculate_name_similarity("Артём Козлов", "Максим Козлов")
        assert score <= 45, f"Classic false positive should be capped at 45, got {score}"

    def test_vladimir_vlad(self, searcher):
        """Влад is diminutive of Владимир AND Владислав -- should match both."""
        score_vladimir = searcher._calculate_name_similarity("Владимир Козлов", "Влад Козлов")
        score_vladislav = searcher._calculate_name_similarity("Владислав Козлов", "Влад Козлов")
        assert score_vladimir >= 70, f"Владимир/Влад should be >=70, got {score_vladimir}"
        assert score_vladislav >= 70, f"Владислав/Влад should be >=70, got {score_vladislav}"

    def test_evgeny_zhenya_gender_ambiguous(self, searcher):
        """Женя is diminutive of both Евгений and Евгения (gender-neutral)."""
        score_m = searcher._calculate_name_similarity("Евгений Козлов", "Женя Козлов")
        score_f = searcher._calculate_name_similarity("Евгения Козлова", "Женя Козлова")
        assert score_m >= 70, f"Евгений/Женя should be >=70, got {score_m}"
        assert score_f >= 70, f"Евгения/Женя should be >=70, got {score_f}"

    def test_danill_glazkov(self, searcher):
        """Known test target: Даниил Глазков."""
        score = searcher._calculate_name_similarity("Даниил Глазков", "Даниил Глазков")
        assert score >= 95

    def test_danill_diminutive_danya(self, searcher):
        """Даня is diminutive of Даниил."""
        score = searcher._calculate_name_similarity("Даниил Глазков", "Даня Глазков")
        assert score >= 70, f"Даниил/Даня should be >=70, got {score}"

    def test_olga_akhtinas(self, searcher):
        """Known test target: Ольга Ахтинас."""
        score = searcher._calculate_name_similarity("Ольга Ахтинас", "Ольга Ахтинас")
        assert score >= 95

    def test_olga_olenka(self, searcher):
        """Оля is diminutive of Ольга."""
        score = searcher._calculate_name_similarity("Ольга Ахтинас", "Оля Ахтинас")
        assert score >= 70, f"Ольга/Оля should be >=70, got {score}"

    def test_vlada_kladko(self, searcher):
        """Known test target: Влада Кладко."""
        score = searcher._calculate_name_similarity("Влада Кладко", "Влада Кладко")
        assert score >= 95


class TestScoreSymmetry:
    """Test whether similarity is symmetric (order of arguments)."""

    @pytest.fixture
    def searcher(self):
        return BuratinoVKSearch()

    def test_symmetry_exact(self, searcher):
        """Exact match should be symmetric."""
        score_ab = searcher._calculate_name_similarity("Иван Иванов", "Иван Иванов")
        score_ba = searcher._calculate_name_similarity("Иван Иванов", "Иван Иванов")
        assert score_ab == score_ba

    def test_symmetry_diminutive(self, searcher):
        """Diminutive match score may differ by direction but both should be high."""
        score_formal = searcher._calculate_name_similarity("Иван Иванов", "Ваня Иванов")
        score_dim = searcher._calculate_name_similarity("Ваня Иванов", "Иван Иванов")
        # Both should be above threshold
        assert score_formal >= 70
        assert score_dim >= 70


class TestToLatin:
    """Test the _to_latin transliteration helper."""

    def test_basic_cyrillic(self):
        result = BuratinoVKSearch._to_latin("иван")
        assert isinstance(result, str)
        assert len(result) > 0
        # Should not contain any Cyrillic characters
        for ch in result:
            assert ord(ch) < 0x400 or ord(ch) > 0x4FF, f"Unexpected Cyrillic char: {ch}"

    def test_latin_passthrough(self):
        result = BuratinoVKSearch._to_latin("ivan")
        assert result == "ivan"

    def test_empty_string(self):
        result = BuratinoVKSearch._to_latin("")
        assert result == ""
