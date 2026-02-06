"""
Unit tests for Phase 2 data source plugins.
Tests HudsonRock, HIBP, and Holehe sources.
"""
import hashlib
import unittest
from unittest.mock import patch, MagicMock

from app.services.phase2.base_source import SourceResult, SourceTier, SourceType
from app.services.phase2.source_manager import SourceManager


class TestSourceManagerDiscovery(unittest.TestCase):

    def test_discovers_sources(self):
        sm = SourceManager()
        self.assertGreater(len(sm.sources), 0)

    def test_discovers_hudsonrock(self):
        sm = SourceManager()
        names = [s.name for s in sm.sources]
        self.assertIn("HudsonRock Cavalier", names)

    def test_discovers_hibp(self):
        sm = SourceManager()
        names = [s.name for s in sm.sources]
        self.assertIn("HIBP Pwned Passwords", names)

    def test_discovers_holehe(self):
        sm = SourceManager()
        names = [s.name for s in sm.sources]
        self.assertIn("Holehe Email Check", names)

    def test_source_status(self):
        sm = SourceManager()
        status = sm.get_source_status()
        self.assertIsInstance(status, list)
        self.assertGreater(len(status), 0)
        for s in status:
            self.assertIn("name", s)
            self.assertIn("tier", s)
            self.assertIn("available", s)


class TestHudsonRockSource(unittest.TestCase):

    def setUp(self):
        from app.services.phase2.sources.breach_api import HudsonRockSource
        self.source = HudsonRockSource()

    def test_is_available(self):
        self.assertTrue(self.source.is_available())

    def test_tier_is_s(self):
        self.assertEqual(self.source.source_tier, SourceTier.S)

    def test_no_api_key_required(self):
        self.assertFalse(self.source.requires_api_key)

    @patch("app.services.phase2.sources.breach_api._get_session")
    def test_search_by_email_found(self, mock_get_session):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "stealers": [{
                "computer_name": "DESKTOP-TEST",
                "operating_system": "Windows 10",
                "date_compromised": "2023-01-15",
                "credentials": [{
                    "url": "https://mail.google.com",
                    "username": "test@gmail.com",
                    "password": "hunter2",
                }],
                "top_logins": ["testuser"],
            }]
        }
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_get_session.return_value = mock_session

        results = self.source.query(email="test@gmail.com")
        self.assertGreater(len(results), 0)
        types = [r.data_type for r in results]
        self.assertIn("email", types)
        self.assertIn("credential", types)

    @patch("app.services.phase2.sources.breach_api._get_session")
    def test_search_by_email_not_found(self, mock_get_session):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": "No results found"}
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_get_session.return_value = mock_session

        results = self.source.query(email="clean@example.com")
        self.assertEqual(len(results), 0)

    @patch("app.services.phase2.sources.breach_api._get_session")
    def test_search_by_email_404(self, mock_get_session):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_get_session.return_value = mock_session

        results = self.source.query(email="missing@example.com")
        self.assertEqual(len(results), 0)

    def test_email_candidates_from_kwargs(self):
        with patch.object(self.source, "_search_by_email", return_value=[]) as mock:
            self.source.query(
                email_candidates=[
                    {"email": "a@test.com"},
                    {"email": "b@test.com"},
                ]
            )
            self.assertEqual(mock.call_count, 2)


class TestHIBPSource(unittest.TestCase):

    def setUp(self):
        from app.services.phase2.sources.breach_api import HIBPSource
        self.source = HIBPSource()

    def test_is_available(self):
        self.assertTrue(self.source.is_available())

    def test_tier_is_b(self):
        self.assertEqual(self.source.source_tier, SourceTier.B)

    def test_no_passwords_returns_empty(self):
        results = self.source.query()
        self.assertEqual(len(results), 0)

    @patch("app.services.phase2.sources.breach_api._get_session")
    def test_password_found_in_breaches(self, mock_get_session):
        password = "password123"
        sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
        suffix = sha1[5:]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = f"AAAAAAA:1\n{suffix}:42\nBBBBBBB:3\n"
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_get_session.return_value = mock_session

        results = self.source.query(passwords=[{"password": password, "email": "test@test.com"}])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].data_type, "credential_validation")
        self.assertTrue(results[0].metadata["password_compromised"])
        self.assertEqual(results[0].metadata["breach_count"], 42)


class TestHoleheSource(unittest.TestCase):

    def setUp(self):
        from app.services.phase2.sources.holehe_check import HoleheCheckSource
        self.source = HoleheCheckSource()

    def test_is_available(self):
        self.assertTrue(self.source.is_available())

    def test_tier_is_b(self):
        self.assertEqual(self.source.source_tier, SourceTier.B)

    def test_no_email_returns_empty(self):
        results = self.source.query()
        self.assertEqual(len(results), 0)

    @patch("app.services.phase2.sources.holehe_check._run_holehe_sync")
    def test_email_found_on_services(self, mock_run):
        mock_run.return_value = [
            {"name": "spotify", "domain": "spotify.com", "exists": True, "emailrecovery": None},
            {"name": "twitter", "domain": "twitter.com", "exists": True, "emailrecovery": None},
            {"name": "facebook", "domain": "facebook.com", "exists": True, "emailrecovery": None},
            {"name": "github", "domain": "github.com", "exists": False, "emailrecovery": None},
        ]
        results = self.source.query(email="real@gmail.com")
        email_results = [r for r in results if r.data_type == "email"]
        profile_results = [r for r in results if r.data_type == "profile"]
        self.assertEqual(len(email_results), 1)
        self.assertTrue(email_results[0].verified)
        self.assertEqual(email_results[0].metadata["total_registered"], 3)
        self.assertIn("spotify", email_results[0].metadata["registered_services"])
        self.assertEqual(len(profile_results), 3)

    @patch("app.services.phase2.sources.holehe_check._run_holehe_sync")
    def test_email_not_found(self, mock_run):
        mock_run.return_value = [
            {"name": "spotify", "domain": "spotify.com", "exists": False},
            {"name": "twitter", "domain": "twitter.com", "exists": False},
        ]
        results = self.source.query(email="fake@nonexistent.com")
        self.assertEqual(len(results), 0)

    @patch("app.services.phase2.sources.holehe_check._run_holehe_sync")
    def test_max_emails_limit(self, mock_run):
        mock_run.return_value = []
        emails = [f"test{i}@gmail.com" for i in range(10)]
        self.source.query(email=emails)
        self.assertEqual(mock_run.call_count, 5)


class TestSourceResult(unittest.TestCase):

    def test_confidence_labels(self):
        r = SourceResult(
            data_type="email", value="test@test.com",
            source_name="Test", source_tier=SourceTier.S,
            confidence=0.95,
        )
        self.assertEqual(r.confidence_label, "very_high")
        r.confidence = 0.75
        self.assertEqual(r.confidence_label, "high")
        r.confidence = 0.55
        self.assertEqual(r.confidence_label, "medium")
        r.confidence = 0.3
        self.assertEqual(r.confidence_label, "low")

    def test_to_dict(self):
        r = SourceResult(
            data_type="email", value="test@test.com",
            source_name="Test", source_tier=SourceTier.S,
            confidence=0.9, verified=True,
            metadata={"key": "value"},
        )
        d = r.to_dict()
        self.assertEqual(d["value"], "test@test.com")
        self.assertEqual(d["source_tier"], "Breach Database")
        self.assertTrue(d["verified"])


class TestDeduplication(unittest.TestCase):

    def test_merges_duplicate_emails(self):
        sm = SourceManager()
        results = [
            SourceResult(
                data_type="email", value="test@gmail.com",
                source_name="Source A", source_tier=SourceTier.S,
                confidence=0.8,
            ),
            SourceResult(
                data_type="email", value="test@gmail.com",
                source_name="Source B", source_tier=SourceTier.B,
                confidence=0.7,
            ),
        ]
        deduped = sm._deduplicate(results)
        self.assertEqual(len(deduped), 1)
        self.assertGreater(deduped[0].confidence, 0.8)
        self.assertEqual(deduped[0].metadata["source_count"], 2)

    def test_different_values_not_merged(self):
        sm = SourceManager()
        results = [
            SourceResult(
                data_type="email", value="a@gmail.com",
                source_name="Source A", source_tier=SourceTier.S,
                confidence=0.8,
            ),
            SourceResult(
                data_type="email", value="b@gmail.com",
                source_name="Source A", source_tier=SourceTier.S,
                confidence=0.7,
            ),
        ]
        deduped = sm._deduplicate(results)
        self.assertEqual(len(deduped), 2)


if __name__ == "__main__":
    unittest.main()
