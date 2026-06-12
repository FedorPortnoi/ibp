"""
Face search (#51 search4faces) status-honesty tests.

The live candidate face path is search4faces_service.search_all_databases.
It discarded the per-database success/error, so an empty result read the same
whether the photo was matched-and-clean or never searched (no API key +
Playwright unavailable). search_all_databases_with_status fixes that, and
_run_face_search threads the status so the dossier can say "поиск не выполнен"
instead of a false "no photos found".
"""

from unittest.mock import patch, MagicMock

import pytest

from app.services.phase2 import search4faces_service as s4f
from app.services.phase2.search4faces_service import (
    Search4FacesResults,
    FaceMatch,
    search_all_databases_with_status,
)


def _result(success, matches=None, error=None):
    return Search4FacesResults(
        success=success, matches=matches or [], database_searched='vkok', error=error,
    )


def _match(url='https://vk.com/id1'):
    return FaceMatch(platform='vk', profile_url=url, similarity_score=0.9)


def _run(side_effects):
    """Run with search_by_photo returning the given per-call results."""
    with patch.object(s4f, 'search_by_photo', side_effect=side_effects), \
         patch.object(s4f.time, 'sleep'):
        return search_all_databases_with_status(image_path='/tmp/x.jpg')


class TestStatusHelper:

    def test_ok_when_matches_found(self):
        matches, status = _run([
            _result(True, [_match('https://vk.com/a')]),
            _result(True, [_match('https://vk.com/b')]),
        ])
        assert status == 'ok'
        assert len(matches) == 2

    def test_empty_when_searched_no_match(self):
        matches, status = _run([_result(True, []), _result(True, [])])
        assert status == 'empty'
        assert matches == []

    def test_unavailable_when_all_databases_fail(self):
        """No API key + Playwright not installed → both DBs fail → unavailable,
        NOT 'no matches'."""
        err = 'Playwright not installed'
        matches, status = _run([_result(False, error=err), _result(False, error=err)])
        assert status == 'unavailable'
        assert matches == []

    def test_no_face_when_photo_has_no_detectable_face(self):
        matches, status = _run([
            _result(True, [], error='No faces detected in image'),
            _result(True, [], error='No faces detected in image'),
        ])
        assert status == 'no_face'

    def test_dedup_across_databases(self):
        same = 'https://vk.com/same'
        matches, status = _run([
            _result(True, [_match(same)]),
            _result(True, [_match(same)]),
        ])
        assert status == 'ok'
        assert len(matches) == 1

    def test_partial_one_db_ok_one_failed_is_ok(self):
        matches, status = _run([
            _result(True, [_match('https://vk.com/x')]),
            _result(False, error='timeout'),
        ])
        assert status == 'ok'
        assert len(matches) == 1


class TestRunFaceSearchThreadsStatus:

    def test_returns_matches_and_status_tuple(self):
        from app.services.candidate.social_analysis import _run_face_search
        with patch(
            'app.services.phase2.search4faces_service.search_all_databases_with_status',
            return_value=([_match('https://vk.com/z')], 'ok'),
        ):
            result = _run_face_search(photo_path='/tmp/x.jpg')
        assert isinstance(result, tuple)
        matches, status = result
        assert status == 'ok'
        assert matches[0]['profile_url'] == 'https://vk.com/z'

    def test_unavailable_propagates(self):
        from app.services.candidate.social_analysis import _run_face_search
        with patch(
            'app.services.phase2.search4faces_service.search_all_databases_with_status',
            return_value=([], 'unavailable'),
        ):
            matches, status = _run_face_search(photo_path='/tmp/x.jpg')
        assert matches == []
        assert status == 'unavailable'

    def test_exception_returns_error_status(self):
        from app.services.candidate.social_analysis import _run_face_search
        with patch(
            'app.services.phase2.search4faces_service.search_all_databases_with_status',
            side_effect=RuntimeError('boom'),
        ):
            matches, status = _run_face_search(photo_path='/tmp/x.jpg')
        assert matches == []
        assert status == 'error'
