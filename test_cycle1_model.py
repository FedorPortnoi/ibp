"""
Cycle 1 Test - Phase 1 Data Model Verification
==============================================
Tests the new ProfileMatch and Phase1Result data structures.
"""

import sys
import os

# Fix Windows Unicode encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.profile import (
    ProfileMatch, Phase1Result, Platform, ConfidenceLevel,
    convert_legacy_results_to_phase1
)

def test_profile_match():
    """Test ProfileMatch creation and confidence scoring."""
    print("=" * 60)
    print("TEST: ProfileMatch Creation and Confidence Scoring")
    print("=" * 60)

    # Test 1: Create a profile with face match and name match
    profile = ProfileMatch(
        url="https://vk.com/tikhon_portnoi",
        platform=Platform.VK,
        username="tikhon_portnoi",
        display_name="Тихон Портной",
        photo_url="https://vk.com/photo.jpg",
        bio="Developer",
        face_match=True,
        face_similarity=85.0,
        name_match=True,
        name_similarity=90.0,
        source="vk_direct"
    )
    profile.calculate_confidence()

    print(f"\n1. VK Profile (face + name match):")
    print(f"   URL: {profile.url}")
    print(f"   Display Name: {profile.display_name}")
    print(f"   Face Match: {profile.face_match} ({profile.face_similarity}%)")
    print(f"   Name Match: {profile.name_match} ({profile.name_similarity}%)")
    print(f"   Confidence Score: {profile.confidence_score}")
    print(f"   Confidence Level: {profile.confidence_level.value}")

    assert profile.confidence_level == ConfidenceLevel.HIGH, "Should be HIGH confidence"
    print("   [PASS] Correctly classified as HIGH confidence")

    # Test 2: Create a profile with name match only
    profile2 = ProfileMatch(
        url="https://ok.ru/tikhon123",
        platform=Platform.OK,
        username="tikhon123",
        display_name="Тихон П.",
        name_match=True,
        name_similarity=60.0,
        source="ok_direct"
    )
    profile2.calculate_confidence()

    print(f"\n2. OK Profile (name match only):")
    print(f"   Display Name: {profile2.display_name}")
    print(f"   Name Match: {profile2.name_match} ({profile2.name_similarity}%)")
    print(f"   Confidence Score: {profile2.confidence_score}")
    print(f"   Confidence Level: {profile2.confidence_level.value}")

    assert profile2.confidence_level == ConfidenceLevel.LOW, "Should be LOW confidence"
    print("   [PASS] Correctly classified as LOW confidence")

    # Test 3: Test to_dict and from_dict
    profile_dict = profile.to_dict()
    restored = ProfileMatch.from_dict(profile_dict)

    print(f"\n3. Serialization Test:")
    print(f"   Original URL: {profile.url}")
    print(f"   Restored URL: {restored.url}")
    assert profile.url == restored.url, "URLs should match"
    assert profile.confidence_score == restored.confidence_score, "Scores should match"
    print("   [PASS] Serialization/deserialization works")

    return True


def test_legacy_conversion():
    """Test conversion from legacy search results."""
    print("\n" + "=" * 60)
    print("TEST: Legacy Result Conversion")
    print("=" * 60)

    # Simulated legacy result from combined_search
    legacy_results = {
        'success': True,
        'accounts': [
            {
                'platform': 'VK',
                'username': 'tikhon_p',
                'url': 'https://vk.com/tikhon_p',
                'display_name': 'Тихон Портной',
                'photo_url': 'https://vk.com/photo1.jpg',
                'exists': True,
                'source': 'vk_direct',
                'face_match': True,
                'face_similarity': 78.5,
                'photos_checked': 5
            },
            {
                'platform': 'Telegram',
                'username': 'tikhon_portnoi',
                'url': 'https://t.me/tikhon_portnoi',
                'display_name': 'Тихон',
                'bio': 'Tech enthusiast',
                'exists': True,
                'source': 'telegram_direct'
            },
            {
                'platform': 'OK',
                'username': 'random_user',
                'url': 'https://ok.ru/random_user',
                'display_name': 'Иван Иванов',
                'exists': True,
                'source': 'ok_direct'
            }
        ],
        'stats': {
            'usernames_searched': 50,
            'raw_accounts': 15,
            'vk_found': 1,
            'telegram_found': 1,
            'ok_found': 1,
            'face_matches': 1,
            'photos_scanned': 10,
            'face_matching_enabled': True,
            'search_time': '2m 30s'
        }
    }

    # Convert to Phase1Result
    phase1_result = convert_legacy_results_to_phase1(
        legacy_results,
        target_name="Тихон Портной",
        target_photo_path="/path/to/photo.jpg"
    )

    print(f"\n1. Converted {len(phase1_result.profiles)} profiles")
    print(f"   Search time: {phase1_result.search_time_seconds}s")
    print(f"   VK found: {phase1_result.vk_found}")
    print(f"   Face matches: {phase1_result.face_matches_found}")

    # Check profiles are sorted by confidence
    print(f"\n2. Profiles sorted by confidence:")
    for i, p in enumerate(phase1_result.profiles):
        print(f"   {i+1}. [{p.platform.value}] {p.display_name} - Score: {p.confidence_score}, Level: {p.confidence_level.value}")

    # Check high confidence filter
    high_conf = phase1_result.get_high_confidence_profiles()
    print(f"\n3. High confidence profiles: {len(high_conf)}")
    for p in high_conf:
        print(f"   - {p.display_name} ({p.url})")

    # Verify the VK profile with face match has highest score
    assert phase1_result.profiles[0].platform == Platform.VK, "VK profile should be first (highest confidence)"
    print("\n   [PASS] Profiles correctly sorted by confidence")

    return True


def test_name_similarity():
    """Test name similarity calculation."""
    print("\n" + "=" * 60)
    print("TEST: Name Similarity Calculation")
    print("=" * 60)

    # Import the function from combined_search
    from app.services.combined_search import calculate_name_similarity

    test_cases = [
        ("Тихон Портной", "Тихон Портной", 100.0),  # Exact match
        ("Тихон Портной", "Тихон П.", 50.0),  # Partial match
        ("Тихон Портной", "Иван Иванов", 0.0),  # No match
        ("Tikhon Portnoi", "tikhon_portnoi", 80.0),  # Username style
        ("Даниил Глазков", "Даня Глазков", 70.0),  # Diminutive
    ]

    print("\n   Target Name          | Found Name        | Expected | Actual | Pass")
    print("   " + "-" * 70)

    all_passed = True
    for target, found, min_expected in test_cases:
        similarity = calculate_name_similarity(target, found)
        passed = similarity >= min_expected * 0.5  # Allow some tolerance
        status = "[PASS]" if passed else "[FAIL]"
        print(f"   {target[:20]:<20} | {found[:17]:<17} | {min_expected:>6.1f}%  | {similarity:>5.1f}% | {status}")
        if not passed:
            all_passed = False

    return all_passed


def main():
    print("\n" + "=" * 60)
    print("      CYCLE 1 TEST SUITE - Phase 1 Data Model")
    print("=" * 60)

    tests = [
        ("ProfileMatch Creation", test_profile_match),
        ("Legacy Result Conversion", test_legacy_conversion),
        ("Name Similarity", test_name_similarity),
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
        print("   ALL TESTS PASSED - Cycle 1 Data Model is working!")
    else:
        print("   SOME TESTS FAILED - Review errors above")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
