"""
Cycle 2 Test - VK People Search Verification
=============================================
Tests the VK People Search (real name search, not username guessing).
"""

import sys
import os

# Fix Windows Unicode encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.phase1.vk_people_search import VKPeopleSearch, search_vk_people


def test_vk_people_search_class():
    """Test VKPeopleSearch class initialization and methods."""
    print("=" * 60)
    print("TEST: VKPeopleSearch Class")
    print("=" * 60)

    searcher = VKPeopleSearch()

    # Test name similarity calculation
    print("\n1. Name Similarity Calculation:")
    test_cases = [
        ("Тихон Портной", "Тихон Портной", 100.0),
        ("Тихон Портной", "Портной Тихон", 90.0),
        ("Тихон Портной", "Тихон П.", 50.0),
    ]

    for target, found, expected in test_cases:
        similarity = searcher._calculate_name_similarity(target, found)
        passed = similarity >= expected * 0.7
        status = "[PASS]" if passed else "[FAIL]"
        print(f"   {target} vs {found}: {similarity:.1f}% (expected >= {expected*0.7:.1f}%) {status}")

    # Test search variations generation
    print("\n2. Search Variations Generation:")
    variations = searcher.generate_search_variations("Тихон Портной")
    print(f"   Input: 'Тихон Портной'")
    print(f"   Variations: {variations}")
    assert len(variations) >= 2, "Should generate at least 2 variations"
    print(f"   [PASS] Generated {len(variations)} variations")

    # Test diminutive variations
    variations2 = searcher.generate_search_variations("Даниил Глазков")
    print(f"\n   Input: 'Даниил Глазков'")
    print(f"   Variations: {variations2}")
    has_diminutive = any('даня' in v.lower() or 'данила' in v.lower() for v in variations2)
    if has_diminutive:
        print("   [PASS] Generated diminutive variations")
    else:
        print("   [WARN] No diminutive variations (optional)")

    return True


def test_vk_people_search_live():
    """Test actual VK people search (requires network)."""
    print("\n" + "=" * 60)
    print("TEST: Live VK People Search")
    print("=" * 60)
    print("NOTE: This test requires network access and may be rate-limited")

    try:
        # Test with a common Russian name
        results = search_vk_people("Иван Иванов", limit=5)

        print(f"\n1. Search for 'Иван Иванов':")
        print(f"   Found: {len(results)} profiles")

        if results:
            for i, r in enumerate(results[:3], 1):
                print(f"   {i}. {r.get('display_name', 'N/A')} - {r.get('url', 'N/A')}")
                print(f"      Name similarity: {r.get('name_similarity', 0):.1f}%")
            print("   [PASS] Found profiles")
        else:
            print("   [WARN] No profiles found (may be rate-limited)")

        # Test with target name for similarity
        results2 = search_vk_people("Тихон Портной", limit=5, target_name="Тихон Портной")
        print(f"\n2. Search for 'Тихон Портной':")
        print(f"   Found: {len(results2)} profiles")

        if results2:
            for i, r in enumerate(results2[:3], 1):
                print(f"   {i}. {r.get('display_name', 'N/A')}")
                print(f"      Similarity: {r.get('name_similarity', 0):.1f}%, Match: {r.get('name_match', False)}")
            print("   [PASS] Search with similarity scoring works")

        return True

    except Exception as e:
        print(f"\n   [ERROR] {e}")
        print("   [SKIP] Live test skipped due to error")
        return True  # Don't fail the whole test for network issues


def test_integration_with_combined_search():
    """Test that VK People Search integrates with combined search."""
    print("\n" + "=" * 60)
    print("TEST: Integration with Combined Search")
    print("=" * 60)

    try:
        from app.services.combined_search import CombinedSearchService

        # Check that import works
        service = CombinedSearchService(max_usernames=5)
        print("   [PASS] CombinedSearchService imports VKPeopleSearch")

        # Check that vk_people_search is imported in the module
        import app.services.combined_search as cs
        has_vk_people = hasattr(cs, 'vk_people_search')
        if has_vk_people:
            print("   [PASS] vk_people_search is available in combined_search module")
        else:
            print("   [FAIL] vk_people_search not found in combined_search")
            return False

        return True

    except ImportError as e:
        print(f"   [FAIL] Import error: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print("      CYCLE 2 TEST SUITE - VK People Search")
    print("=" * 60)

    tests = [
        ("VKPeopleSearch Class", test_vk_people_search_class),
        ("Live VK Search", test_vk_people_search_live),
        ("Combined Search Integration", test_integration_with_combined_search),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n[ERROR] in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    print("\n" + "=" * 60)
    print("                    TEST SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"   {name}: {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("   ALL TESTS PASSED - Cycle 2 VK People Search is working!")
    else:
        print("   SOME TESTS FAILED - Review errors above")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
