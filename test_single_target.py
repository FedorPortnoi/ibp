"""
IBP Single Target Test - Full Phase 1 + Phase 2
================================================
Tests one target with full Phase 1 to get real profiles.
"""

import sys
import os
import time
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_single_target_test():
    """Test with real Phase 1 profiles."""
    from app.services.combined_search import CombinedSearchService
    from app.services.phase2.per_profile_search import PerProfileSearchService

    target_name = "Angelina Pilyushina"
    photo_path = r"C:\Users\fedor\ibp\gel.jpg"

    print(f"\n{'='*60}")
    print(f"FULL TEST: {target_name}")
    print(f"Photo: {photo_path}")
    print(f"{'='*60}")

    # Phase 1: Find real profiles
    print("\n[PHASE 1] Finding social media profiles...")
    start_time = time.time()

    try:
        phase1_service = CombinedSearchService()
        results = phase1_service.search(
            target_name=target_name,
            target_photo_path=photo_path if os.path.exists(photo_path) else None
        )

        profiles = []
        if isinstance(results, dict):
            profiles = results.get('results', results.get('accounts', []))
        elif hasattr(results, 'profiles'):
            profiles = results.profiles
        elif isinstance(results, list):
            profiles = results

        # Normalize to dicts
        profile_dicts = []
        for p in profiles:
            if isinstance(p, dict):
                profile_dicts.append(p)
            else:
                profile_dicts.append({
                    'platform': getattr(p, 'platform', ''),
                    'username': getattr(p, 'username', ''),
                    'url': getattr(p, 'url', '')
                })

        phase1_time = time.time() - start_time
        print(f"Phase 1 found {len(profile_dicts)} profiles in {phase1_time:.1f}s")

        for i, p in enumerate(profile_dicts[:10]):
            print(f"  {i+1}. [{p.get('platform', '?')}] {p.get('username', '')}: {p.get('url', '')[:60]}")

    except Exception as e:
        print(f"Phase 1 ERROR: {e}")
        import traceback
        traceback.print_exc()
        return

    if not profile_dicts:
        print("No profiles found - cannot test Phase 2")
        return

    # Phase 2: Per-profile contact discovery
    print(f"\n[PHASE 2] Per-profile contact discovery...")
    print(f"Testing {min(5, len(profile_dicts))} profiles")

    phase2_service = PerProfileSearchService()

    try:
        results = phase2_service.investigate_all_profiles(
            profiles=profile_dicts[:5],
            target_name=target_name,
            max_profiles=5
        )

        # Display results
        print(f"\n{'='*60}")
        print("PER-PROFILE RESULTS")
        print(f"{'='*60}")

        for pr in results.profile_results:
            status = "PASS" if pr.is_complete else "FAIL"
            print(f"\n[{status}] {pr.platform}/{pr.username}")
            print(f"  URL: {pr.profile_url}")
            print(f"  Verified Emails: {len(pr.verified_emails)}")
            for e in pr.verified_emails[:5]:
                print(f"    - {e.email} ({e.verification_method})")
            print(f"  Phones: {len(pr.phones)}")
            for p in pr.phones:
                print(f"    - {p.number} ({p.source})")

        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Profiles: {results.passing_profiles}/{results.total_profiles} passing")
        print(f"Verified emails: {results.total_verified_emails}")
        print(f"Phones: {results.total_phones}")
        print(f"Status: {'ALL PASS' if results.all_pass else 'NEEDS WORK'}")

    finally:
        phase2_service.close()


if __name__ == "__main__":
    run_single_target_test()
