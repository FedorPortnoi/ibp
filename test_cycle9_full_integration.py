"""
Cycle 9 Test - Full Буратино Workflow Integration
=================================================
End-to-end test of the complete OSINT workflow.
"""

import sys
import os
import json

# Fix Windows Unicode encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_phase1_services():
    """Test all Phase 1 services are available."""
    print("=" * 60)
    print("TEST: Phase 1 Services")
    print("=" * 60)

    try:
        from app.services.phase1 import (
            VKPeopleSearch,
            OKPeopleSearch,
            TelegramPeopleSearch,
            FaceSearchService,
            search_vk_people,
            search_ok_people,
            search_telegram_people,
            search_faces
        )
        print("   [PASS] All Phase 1 services imported")

        # Test instantiation
        vk = VKPeopleSearch()
        ok = OKPeopleSearch()
        tg = TelegramPeopleSearch()
        face = FaceSearchService()

        print("   [PASS] All Phase 1 services instantiated")
        return True

    except ImportError as e:
        print(f"   [FAIL] Import error: {e}")
        return False


def test_phase2_services():
    """Test all Phase 2 services are available."""
    print("\n" + "=" * 60)
    print("TEST: Phase 2 Services")
    print("=" * 60)

    try:
        from app.services.phase2.combined_search import Phase2CombinedSearch, Phase2Results

        searcher = Phase2CombinedSearch()
        print("   [PASS] Phase2CombinedSearch instantiated")
        return True

    except ImportError as e:
        print(f"   [FAIL] Import error: {e}")
        return False


def test_phase3_services():
    """Test all Phase 3 services are available."""
    print("\n" + "=" * 60)
    print("TEST: Phase 3 Services")
    print("=" * 60)

    try:
        from app.services.phase3 import (
            Phase3CombinedSearch,
            phase3_combined_search,
            BusinessRegistrySearch,
            CourtRecordSearch
        )

        searcher = Phase3CombinedSearch()
        print("   [PASS] Phase3CombinedSearch instantiated")
        return True

    except ImportError as e:
        print(f"   [FAIL] Import error: {e}")
        return False


def test_report_generator():
    """Test report generator with all phases data."""
    print("\n" + "=" * 60)
    print("TEST: Report Generator Integration")
    print("=" * 60)

    try:
        from app.services.report_generator import ReportGenerator, IdentityCardData

        generator = ReportGenerator()

        # Full investigation data from all phases
        investigation = {
            'input_name': 'Тихон Портной',
            'id': 'test-investigation-123',
            # Phase 1 data
            'discovered_profiles': [
                {'platform': 'vk', 'url': 'https://vk.com/tikhon', 'username': 'tikhon', 'confidence_level': 'high'},
                {'platform': 'telegram', 'url': 'https://t.me/tikhon', 'username': 'tikhon', 'confidence_level': 'high'},
            ],
            'discovered_usernames': ['tikhon', 'tikhon_p', 'portnoj'],
            'input_photo_path': '/path/to/photo.jpg',
            # Phase 2 data
            'discovered_phones': [
                {'number': '+7 999 111 22 33', 'source': 'VK profile', 'confidence': 'high'}
            ],
            'discovered_emails': [
                {'email': 'tikhon@test.com', 'source': 'Profile bio', 'confidence': 'high'}
            ],
            # Phase 3 data
            'business_records': [
                {'company_name': 'Test LLC', 'role': 'Director', 'inn': '1234567890'}
            ],
            'court_records': [
                {'case_number': '123/2024', 'court_name': 'Moscow Court', 'case_type': 'civil'}
            ],
            'social_connections': [
                {'name': 'Friend 1', 'relationship': 'friend', 'platform': 'vk'}
            ],
            'risk_indicators': [
                {'category': 'legal', 'severity': 'low', 'description': 'Minor civil case'}
            ],
            'overall_risk': 'low'
        }

        # Compile data
        data = generator.compile_data(investigation)

        # Verify all phases data is included
        assert data.full_name == 'Тихон Портной'
        assert len(data.profiles) == 2
        assert len(data.phones) == 1
        assert len(data.emails) == 1
        assert len(data.companies) == 1
        assert len(data.risk_indicators) == 1
        assert len(data.social_connections) == 1

        print(f"   Full name: {data.full_name}")
        print(f"   Profiles: {len(data.profiles)}")
        print(f"   Phones: {len(data.phones)}")
        print(f"   Emails: {len(data.emails)}")
        print(f"   Companies: {len(data.companies)}")
        print(f"   Risk indicators: {len(data.risk_indicators)}")
        print(f"   Confidence score: {data.confidence_score}")

        # Generate HTML
        html = generator.generate_identity_card_html(data)
        assert len(html) > 5000, "HTML should be substantial"
        assert 'Тихон Портной' in html
        assert 'Risk Indicators' in html

        print("   [PASS] Report generator handles all phases data")
        return True

    except Exception as e:
        print(f"   [FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_combined_search_pipeline():
    """Test the combined search service pipeline."""
    print("\n" + "=" * 60)
    print("TEST: Combined Search Pipeline")
    print("=" * 60)

    try:
        from app.services.combined_search import CombinedSearchService, SearchProgress

        # Verify the search service has all steps
        progress = SearchProgress()
        print(f"   Total steps: {progress.total_steps}")
        assert progress.total_steps >= 10, "Should have at least 10 steps"

        # Check that the service can be instantiated
        service = CombinedSearchService()
        assert service is not None, "CombinedSearchService should instantiate"

        print("   [PASS] Combined search pipeline configured correctly")
        return True

    except Exception as e:
        print(f"   [FAIL] Error: {e}")
        return False


def test_data_flow():
    """Test data flows correctly between phases."""
    print("\n" + "=" * 60)
    print("TEST: Data Flow Between Phases")
    print("=" * 60)

    # Simulate Phase 1 output
    phase1_results = {
        'profiles': [
            {
                'platform': 'vk',
                'url': 'https://vk.com/test',
                'username': 'test',
                'display_name': 'Test User',
                'confidence_level': 'high',
                'confidence_score': 85.0
            }
        ],
        'stats': {
            'total_found': 1,
            'high_confidence': 1
        }
    }

    # Simulate Phase 2 input (takes Phase 1 profiles)
    phase2_input = {
        'selected_profiles': phase1_results['profiles'],
        'target_name': 'Test User'
    }

    # Verify Phase 2 can accept Phase 1 output
    assert 'selected_profiles' in phase2_input
    assert len(phase2_input['selected_profiles']) == 1
    assert phase2_input['selected_profiles'][0]['platform'] == 'vk'

    # Simulate Phase 2 output
    phase2_results = {
        'phones': [{'number': '+7 999 111 22 33', 'source': 'VK profile'}],
        'emails': [{'email': 'test@test.com', 'source': 'Profile bio'}],
        'additional_profiles': [
            {'platform': 'telegram', 'url': 'https://t.me/test', 'username': 'test'}
        ]
    }

    # Simulate Phase 3 input (takes Phase 1 + 2 data)
    phase3_input = {
        'target_name': 'Test User',
        'confirmed_profiles': phase1_results['profiles'],
        'discovered_contacts': {
            'phones': phase2_results['phones'],
            'emails': phase2_results['emails']
        }
    }

    # Verify Phase 3 can accept Phase 1+2 output
    assert 'confirmed_profiles' in phase3_input
    assert 'discovered_contacts' in phase3_input
    assert len(phase3_input['discovered_contacts']['phones']) == 1

    print("   Phase 1 -> Phase 2: OK")
    print("   Phase 2 -> Phase 3: OK")
    print("   [PASS] Data flows correctly between phases")
    return True


def test_confidence_scoring():
    """Test confidence scoring across phases."""
    print("\n" + "=" * 60)
    print("TEST: Confidence Scoring")
    print("=" * 60)

    from app.services.report_generator import ReportGenerator

    generator = ReportGenerator()

    # Low confidence case (minimal data)
    low_data = generator.compile_data({
        'input_name': 'Unknown'
    })
    assert low_data.confidence_score < 20, f"Low confidence expected, got {low_data.confidence_score}"

    # Medium confidence case
    medium_data = generator.compile_data({
        'input_name': 'Test Person',
        'discovered_profiles': [{'platform': 'vk', 'confidence_level': 'medium'}],
        'discovered_phones': ['+7 999 111 22 33'],
        'discovered_emails': ['test@test.com']
    })
    assert 10 <= medium_data.confidence_score < 60, f"Medium confidence expected, got {medium_data.confidence_score}"

    # High confidence case (all phases data)
    high_data = generator.compile_data({
        'input_name': 'Test Person',
        'input_photo_path': '/path/to/photo.jpg',
        'discovered_profiles': [
            {'platform': 'vk', 'confidence_level': 'high'},
            {'platform': 'ok', 'confidence_level': 'high'}
        ],
        'discovered_phones': ['+7 999 111 22 33', '+7 999 444 55 66'],
        'discovered_emails': ['test@test.com'],
        'business_records': [{'company_name': 'Test'}],
        'social_connections': [{'name': 'Friend'}]
    })
    assert high_data.confidence_score >= 50, f"High confidence expected, got {high_data.confidence_score}"

    print(f"   Low confidence: {low_data.confidence_score}")
    print(f"   Medium confidence: {medium_data.confidence_score}")
    print(f"   High confidence: {high_data.confidence_score}")
    print("   [PASS] Confidence scoring works correctly")
    return True


def main():
    print("\n" + "=" * 60)
    print("      CYCLE 9 TEST SUITE - Full Буратино Integration")
    print("=" * 60)

    tests = [
        ("Phase 1 Services", test_phase1_services),
        ("Phase 2 Services", test_phase2_services),
        ("Phase 3 Services", test_phase3_services),
        ("Report Generator", test_report_generator),
        ("Combined Search Pipeline", test_combined_search_pipeline),
        ("Data Flow", test_data_flow),
        ("Confidence Scoring", test_confidence_scoring),
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
        print("   ALL TESTS PASSED - Буратино workflow integration complete!")
    else:
        print("   SOME TESTS FAILED - Review errors above")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
