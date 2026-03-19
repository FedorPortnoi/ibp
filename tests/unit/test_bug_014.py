"""Test BUG-014: Snoop fallback + Maigret wiring."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def test_snoop_availability_check():
    """Snoop availability check must not crash."""
    from app.services.snoop_search import SnoopSearchService
    snoop = SnoopSearchService()
    available = snoop.available
    print(f"Snoop available: {available}")
    print(f"Snoop dir: {snoop.snoop_dir}")
    print(f"Snoop script: {snoop.snoop_script}")
    # Must not crash - pass regardless of availability
    assert isinstance(available, bool)
    print("PASS: Snoop availability check does not crash")


def test_snoop_graceful_fallback():
    """Snoop search_username must return [] when not available."""
    from app.services.snoop_search import SnoopSearchService
    snoop = SnoopSearchService()
    if not snoop.available:
        results = snoop.search_username("test_user_xyz")
        assert results == [], f"FAIL: expected [], got {results}"
        print("PASS: Snoop returns [] when not available")
    else:
        print("SKIP: Snoop is available, can't test fallback")


def test_maigret_availability_check():
    """Maigret availability check must not crash."""
    from app.services.maigret_search import MaigretSearchService
    maigret = MaigretSearchService()
    available = maigret.available
    print(f"Maigret available: {available}")
    print(f"Maigret path: {maigret._maigret_path}")
    assert isinstance(available, bool)
    print("PASS: Maigret availability check does not crash")


def test_maigret_graceful_fallback():
    """Maigret search_username must return [] when not available."""
    from app.services.maigret_search import MaigretSearchService
    maigret = MaigretSearchService()
    if not maigret.available:
        results = maigret.search_username("test_user_xyz")
        assert results == [], f"FAIL: expected [], got {results}"
        print("PASS: Maigret returns [] when not available")
    else:
        # If maigret IS available, test a quick search
        print("Maigret IS available - running quick test...")
        results = maigret.search_username("test_nonexistent_user_xyz123", timeout=30)
        assert isinstance(results, list), f"FAIL: expected list, got {type(results)}"
        print(f"PASS: Maigret returned {len(results)} results (expected for nonexistent user)")


def test_maigret_standalone_detection():
    """Maigret standalone detection via shutil.which."""
    import shutil
    maigret_on_path = shutil.which('maigret')
    print(f"Maigret on PATH: {maigret_on_path}")
    from app.services.maigret_search import _resolve_maigret
    resolved = _resolve_maigret()
    print(f"Resolved maigret path: {resolved}")
    assert resolved is not None, "Maigret should be resolvable"
    assert resolved in ('module', 'standalone') or os.path.exists(resolved), \
        f"Resolved path should be valid: {resolved}"
    print("PASS: Maigret resolution works correctly")


def test_social_analysis_imports():
    """Social analysis module must import without errors."""
    from app.services.candidate.social_analysis import (
        _run_snoop_search, _run_maigret_search, _run_sherlock_search
    )
    # Each function must handle missing tools gracefully
    print("PASS: Social analysis functions import correctly")


if __name__ == '__main__':
    test_snoop_availability_check()
    test_snoop_graceful_fallback()
    test_maigret_availability_check()
    test_maigret_graceful_fallback()
    test_maigret_standalone_detection()
    test_social_analysis_imports()
    print("\nAll BUG-014 tests PASSED")
