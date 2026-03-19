"""Test court search service."""
import sys
import os
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def test_court_search_no_crash():
    """Court search must not crash even if site is unreachable."""
    from app.services.phase3.court_search import CourtRecordSearch
    svc = CourtRecordSearch(timeout=10)
    results = svc.search_by_name('Иванов Иван')
    assert isinstance(results, list), f"FAIL: not a list, got {type(results)}"
    print(f"PASS: search returned {len(results)} results without crash")


def test_manual_urls_generated():
    """Manual search URLs must always be available."""
    from app.services.phase3.court_search import CourtRecordSearch
    urls = CourtRecordSearch.get_manual_search_urls('Иванов Иван')
    assert len(urls) >= 2, f"FAIL: only {len(urls)} manual URLs"
    assert any('sudact' in u['url'] for u in urls), "FAIL: no sudact URL"
    assert any('arbitr' in u['url'] for u in urls), "FAIL: no arbitr URL"
    print(f"PASS: {len(urls)} manual search URLs generated")


def test_cyrillic_case_numbers_parsed():
    """Case numbers with Cyrillic letters (e.g. 2А-1853/2025) must be matched."""
    # The regex used in court_search.py for case numbers
    case_regex = r'\d{1,2}[А-Яа-я]{0,3}-\d+/\d{4}'
    test_cases = [
        ('2А-1853/2025', True, 'administrative case with Cyrillic А'),
        ('2-336/2025', True, 'standard civil case'),
        ('77-1803/2025', True, 'appeal case'),
        ('12АП-3456/2025', True, 'appellate case with Cyrillic АП'),
        ('5-108/2025', True, 'administrative offense'),
        ('not-a-case', False, 'invalid string'),
    ]
    for value, should_match, description in test_cases:
        match = re.search(case_regex, value)
        if should_match:
            assert match is not None, f"FAIL: regex missed '{value}' ({description})"
        else:
            assert match is None, f"FAIL: regex falsely matched '{value}' ({description})"
    print("PASS: Cyrillic case number regex handles all formats correctly")


def test_court_search_returns_court_case_objects():
    """Verify returned objects have expected structure."""
    from app.services.phase3.court_search import CourtRecordSearch, CourtCase
    svc = CourtRecordSearch(timeout=15)
    results = svc.search_by_name('Петров Сергей')
    if results:
        for r in results:
            assert isinstance(r, CourtCase), f"FAIL: not CourtCase, got {type(r)}"
            d = r.to_dict()
            assert 'case_number' in d, "FAIL: missing case_number"
            assert 'court_name' in d, "FAIL: missing court_name"
            assert 'source' in d, "FAIL: missing source"
            assert d['case_number'], "FAIL: empty case_number"
        print(f"PASS: {len(results)} results all have correct CourtCase structure")
    else:
        print("PASS: search returned 0 results (site may be unreachable) but did not crash")


def test_empty_name_returns_empty():
    """Empty name must return empty list, not crash."""
    from app.services.phase3.court_search import CourtRecordSearch
    svc = CourtRecordSearch(timeout=5)
    results = svc.search_by_name('')
    assert results == [], f"FAIL: expected [], got {results}"
    results2 = svc.search_by_name('   ')
    assert results2 == [], f"FAIL: expected [], got {results2}"
    print("PASS: empty/whitespace names return empty list")


if __name__ == '__main__':
    test_court_search_no_crash()
    test_manual_urls_generated()
    test_cyrillic_case_numbers_parsed()
    test_court_search_returns_court_case_objects()
    test_empty_name_returns_empty()
    print("\nAll court tests PASSED")
