"""
IBP Phase 2 Quick Test - Skip Phase 1
=====================================
Tests Phase 2 with pre-defined profiles for faster iteration.
"""

import sys
import os
import time
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add the app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Pre-defined profiles to test (simulating Phase 1 results)
# These are common Russian VK/OK profiles that likely exist
TEST_DATA = [
    {
        "target_name": "Alyona Smirnova",
        "profiles": [
            {"platform": "vk", "username": "alenka_smirnova", "url": "https://vk.com/alenka_smirnova"},
            {"platform": "vk", "username": "alyona.sm", "url": "https://vk.com/alyona.sm"},
            {"platform": "telegram", "username": "alenka_s", "url": "https://t.me/alenka_s"},
        ]
    },
    {
        "target_name": "Danya Mescheryakov",
        "profiles": [
            {"platform": "vk", "username": "danya_mesch", "url": "https://vk.com/danya_mesch"},
            {"platform": "vk", "username": "d.mescheryakov", "url": "https://vk.com/d.mescheryakov"},
            {"platform": "telegram", "username": "danya_m", "url": "https://t.me/danya_m"},
        ]
    },
    {
        "target_name": "Angelina Pilyushina",
        "profiles": [
            {"platform": "vk", "username": "angelina_p", "url": "https://vk.com/angelina_p"},
            {"platform": "vk", "username": "pilyushina_gel", "url": "https://vk.com/pilyushina_gel"},
            {"platform": "ok", "username": "angelina.pilyushina", "url": "https://ok.ru/angelina.pilyushina"},
        ]
    }
]


def run_per_profile_test(target_name: str, profiles: list):
    """Run Phase 2 per-profile test."""
    from app.services.phase2.per_profile_search import PerProfileSearchService

    print(f"\n{'='*60}")
    print(f"Testing: {target_name}")
    print(f"Profiles: {len(profiles)}")
    print(f"{'='*60}")

    service = PerProfileSearchService()

    try:
        results = service.investigate_all_profiles(
            profiles=profiles,
            target_name=target_name,
            max_profiles=5
        )

        # Print detailed results
        print(f"\n--- RESULTS ---")
        for pr in results.profile_results:
            status = "PASS" if pr.is_complete else "FAIL"
            print(f"\n[{status}] {pr.platform}/{pr.username}")
            print(f"  URL: {pr.profile_url}")
            print(f"  Verified Emails: {len(pr.verified_emails)}")
            for e in pr.verified_emails:
                print(f"    - {e.email} (via {e.verification_method})")
            print(f"  Phones: {len(pr.phones)}")
            for p in pr.phones:
                print(f"    - {p.number} ({p.source})")
            if pr.errors:
                print(f"  Errors: {pr.errors[:2]}")

        print(f"\n--- SUMMARY ---")
        print(f"Passing profiles: {results.passing_profiles}/{results.total_profiles}")
        print(f"Total verified emails: {results.total_verified_emails}")
        print(f"Total phones: {results.total_phones}")
        print(f"Time: {results.total_time:.1f}s")
        print(f"Status: {'ALL PASS' if results.all_pass else 'INCOMPLETE'}")

        return results

    finally:
        service.close()


def main():
    print("\n" + "#"*65)
    print("#  IBP PHASE 2 QUICK TEST (skipping Phase 1)")
    print("#"*65)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    all_results = []

    for test_case in TEST_DATA:
        results = run_per_profile_test(test_case['target_name'], test_case['profiles'])
        all_results.append({
            'target': test_case['target_name'],
            'all_pass': results.all_pass,
            'passing': results.passing_profiles,
            'total': results.total_profiles,
            'emails': results.total_verified_emails,
            'phones': results.total_phones
        })

    # Final summary
    print("\n" + "="*65)
    print("FINAL SUMMARY")
    print("="*65)

    total_pass = sum(1 for r in all_results if r['all_pass'])
    print(f"Targets passing: {total_pass}/{len(all_results)}")
    print(f"Total verified emails: {sum(r['emails'] for r in all_results)}")
    print(f"Total phones: {sum(r['phones'] for r in all_results)}")

    if total_pass == len(all_results):
        print("\nOVERALL: SUCCESS - All targets have complete profiles")
        return 0
    else:
        print("\nOVERALL: NEEDS IMPROVEMENT")
        return 1


if __name__ == "__main__":
    sys.exit(main())
