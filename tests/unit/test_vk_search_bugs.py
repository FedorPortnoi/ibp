"""
Tests for VK search bugs:
  BUG 1: Screen name guessing threshold (should use filtered count < 3, not < 10)
  BUG 2: Name filter too loose (first_name threshold should be 0.65, not 0.6)
"""

import pytest
from unittest.mock import patch, MagicMock


# ── BUG 1: Screen name guessing threshold ──────────────────────────


class TestScreenNameGuessingThreshold:
    """Screen name guessing should only run when FILTERED results < 3."""

    def _make_profile(self, vk_id, first, last):
        return {
            'id': vk_id,
            'first_name': first,
            'last_name': last,
            'domain': f'id{vk_id}',
        }

    def test_guessing_runs_when_filtered_low_but_raw_high(self):
        """If newsfeed returns 15 raw IDs but only 2 pass name filter,
        screen_name guessing MUST still run (2 < 3)."""
        from app.services.phase1.vk_web_search import VKWebSearch

        searcher = VKWebSearch(service_token='fake_token')
        searcher._session = MagicMock()

        # _playwright_search returns 0 (no web token)
        # _newsfeed_search returns 15 raw user IDs (high raw count)
        raw_newsfeed_ids = list(range(1000, 1015))

        # _enrich_profiles returns only 2 verified profiles (low filtered count)
        verified = [
            self._make_profile(1000, 'Иван', 'Иванов'),
            self._make_profile(1001, 'Иван', 'Иванов'),
        ]

        # _guess_screen_names returns some new IDs
        guessed_ids = [2000, 2001]
        guessed_profiles = [
            self._make_profile(2000, 'Иван', 'Иванов'),
        ]

        with patch.object(searcher, '_playwright_search', return_value=[]) as mock_pw, \
             patch.object(searcher, '_newsfeed_search', return_value=raw_newsfeed_ids), \
             patch.object(searcher, '_enrich_profiles') as mock_enrich, \
             patch.object(searcher, '_guess_screen_names', return_value=guessed_ids) as mock_guess:

            # First call to _enrich_profiles (for people_search + newsfeed)
            # Second call (for screen_name guessed IDs)
            mock_enrich.side_effect = [verified, guessed_profiles]

            profiles, count = searcher.search('Иван Иванов')

            # Screen name guessing MUST have been called (2 verified < 3)
            mock_guess.assert_called_once_with('Иван Иванов')

    def test_guessing_skipped_when_filtered_sufficient(self):
        """If we have 3+ verified profiles, screen_name guessing should be skipped."""
        from app.services.phase1.vk_web_search import VKWebSearch

        searcher = VKWebSearch(service_token='fake_token')
        searcher._session = MagicMock()

        verified = [
            self._make_profile(i, 'Иван', 'Иванов')
            for i in range(1000, 1005)  # 5 verified profiles
        ]

        with patch.object(searcher, '_playwright_search', return_value=[]), \
             patch.object(searcher, '_newsfeed_search', return_value=list(range(1000, 1020))), \
             patch.object(searcher, '_enrich_profiles', return_value=verified), \
             patch.object(searcher, '_guess_screen_names') as mock_guess:

            profiles, count = searcher.search('Иван Иванов')

            # Screen name guessing should NOT be called (5 verified >= 3)
            mock_guess.assert_not_called()

    def test_guessing_runs_at_boundary_two_results(self):
        """Exactly 2 verified results — guessing MUST run (2 < 3)."""
        from app.services.phase1.vk_web_search import VKWebSearch

        searcher = VKWebSearch(service_token='fake_token')
        searcher._session = MagicMock()

        verified = [
            self._make_profile(1000, 'Иван', 'Иванов'),
            self._make_profile(1001, 'Иван', 'Иванов'),
        ]

        with patch.object(searcher, '_playwright_search', return_value=[]), \
             patch.object(searcher, '_newsfeed_search', return_value=list(range(1000, 1010))), \
             patch.object(searcher, '_enrich_profiles') as mock_enrich, \
             patch.object(searcher, '_guess_screen_names', return_value=[]) as mock_guess:

            mock_enrich.return_value = verified
            searcher.search('Иван Иванов')
            mock_guess.assert_called_once()

    def test_guessing_skipped_at_boundary_three_results(self):
        """Exactly 3 verified results — guessing should NOT run (3 >= 3)."""
        from app.services.phase1.vk_web_search import VKWebSearch

        searcher = VKWebSearch(service_token='fake_token')
        searcher._session = MagicMock()

        verified = [
            self._make_profile(1000, 'Иван', 'Иванов'),
            self._make_profile(1001, 'Иван', 'Иванов'),
            self._make_profile(1002, 'Иван', 'Иванов'),
        ]

        with patch.object(searcher, '_playwright_search', return_value=[]), \
             patch.object(searcher, '_newsfeed_search', return_value=list(range(1000, 1015))), \
             patch.object(searcher, '_enrich_profiles', return_value=verified), \
             patch.object(searcher, '_guess_screen_names') as mock_guess:

            searcher.search('Иван Иванов')
            mock_guess.assert_not_called()


# ── BUG 2: Name filter threshold ───────────────────────────────────


class TestNameFilterThreshold:
    """Name matching should reject loose first-name matches (threshold 0.65)."""

    def test_reject_different_last_name(self):
        """'Иван Иванов' must NOT match 'Ивана Петрова' (different last name)."""
        from app.services.phase1.vk_web_search import verify_profile_name_matches_query

        profile = {'first_name': 'Ивана', 'last_name': 'Петрова'}
        assert not verify_profile_name_matches_query(profile, 'иван', 'иванов')

    def test_reject_different_last_name_kozlova(self):
        """'Иван Иванов' must NOT match 'Иванка Козлова' (different last name)."""
        from app.services.phase1.vk_web_search import verify_profile_name_matches_query

        profile = {'first_name': 'Иванка', 'last_name': 'Козлова'}
        assert not verify_profile_name_matches_query(profile, 'иван', 'иванов')

    def test_accept_diminutive_first_name(self):
        """'Иван Иванов' SHOULD match 'Ваня Иванов' (diminutive)."""
        from app.services.phase1.vk_web_search import verify_profile_name_matches_query

        profile = {'first_name': 'Ваня', 'last_name': 'Иванов'}
        assert verify_profile_name_matches_query(profile, 'иван', 'иванов')

    def test_accept_transliterated_name(self):
        """'Иван Иванов' SHOULD match 'Ivan Ivanov' (transliterated)."""
        from app.services.phase1.vk_web_search import verify_profile_name_matches_query

        profile = {'first_name': 'Ivan', 'last_name': 'Ivanov'}
        assert verify_profile_name_matches_query(profile, 'иван', 'иванов')

    def test_reject_maksim_vs_mark(self):
        """'Максим' should NOT match 'Марк' — SequenceMatcher ~0.60, below 0.65."""
        from app.services.phase1.vk_web_search import verify_profile_name_matches_query

        profile = {'first_name': 'Марк', 'last_name': 'Козлов'}
        assert not verify_profile_name_matches_query(profile, 'максим', 'козлов')

    def test_reject_nikolay_vs_nikita(self):
        """'Николай' should NOT match 'Никита' — SequenceMatcher ~0.62, below 0.65."""
        from app.services.phase1.vk_web_search import verify_profile_name_matches_query

        profile = {'first_name': 'Никита', 'last_name': 'Сидоров'}
        assert not verify_profile_name_matches_query(profile, 'николай', 'сидоров')

    def test_accept_exact_match(self):
        """Exact name match must always pass."""
        from app.services.phase1.vk_web_search import verify_profile_name_matches_query

        profile = {'first_name': 'Дмитрий', 'last_name': 'Козлов'}
        assert verify_profile_name_matches_query(profile, 'дмитрий', 'козлов')

    def test_accept_dima_for_dmitriy(self):
        """Diminutive 'Дима' should match 'Дмитрий'."""
        from app.services.phase1.vk_web_search import verify_profile_name_matches_query

        profile = {'first_name': 'Дима', 'last_name': 'Козлов'}
        assert verify_profile_name_matches_query(profile, 'дмитрий', 'козлов')

    def test_reject_completely_different_names(self):
        """'Сергей Сидоров' must NOT match 'Андрей Сидоров' (different first name)."""
        from app.services.phase1.vk_web_search import verify_profile_name_matches_query

        profile = {'first_name': 'Андрей', 'last_name': 'Сидоров'}
        assert not verify_profile_name_matches_query(profile, 'сергей', 'сидоров')
