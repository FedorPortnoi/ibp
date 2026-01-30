"""
Phase 2 Only Testing Script - Cycle 2
======================================
Tests Phase 2 without Phase 1 (which has slow face recognition imports).
Uses mock profile data but improved phone discovery via VK name search.
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

# Test targets - using 1 profile per target for realistic testing
# Success criteria: At least 1 email AND 1 phone per target
TEST_TARGETS = [
    {
        "name": "Svetlana Axtinas",
        "photo": r"C:\Users\fedor\ibp\photo_2026-01-29_16-58-19.jpg",
        "profiles": [
            {"platform": "vk", "username": "svetlana", "url": "https://vk.com/svetlana"},
        ]
    },
    {
        "name": "Tikhon Portnoi",
        "photo": r"C:\Users\fedor\ibp\photo_2026-01-29_17-21-02.jpg",
        "profiles": [
            {"platform": "vk", "username": "tikhon", "url": "https://vk.com/tikhon"},
        ]
    },
    {
        "name": "Daniil Glazkov",
        "photo": r"C:\Users\fedor\ibp\photo_2026-01-29_17-23-44.jpg",
        "profiles": [
            {"platform": "vk", "username": "daniil_glazkov", "url": "https://vk.com/daniil_glazkov"},
        ]
    }
]


def run_phase2_search(selected_profiles: list, target_name: str, photo_path: str = None) -> dict:
    """Run Phase 2 search to find emails and phones."""
    from app.services.phase2.combined_search import Phase2CombinedSearch

    print(f"\n{'='*60}")
    print(f"PHASE 2: Contact Discovery for {target_name}")
    print(f"Testing {len(selected_profiles)} profiles")
    print(f"{'='*60}")

    start_time = time.time()

    print("\nProfiles for Phase 2:")
    for i, p in enumerate(selected_profiles):
        print(f"  {i+1}. [{p.get('platform', '?')}] {p.get('username', '?')}")

    # Initialize Phase 2 search
    searcher = Phase2CombinedSearch()

    print("\nRunning Phase 2 investigate_fast()...")
    results = searcher.investigate_fast(
        selected_profiles=selected_profiles,
        target_name=target_name,
        target_photo_path=photo_path if photo_path and os.path.exists(photo_path) else None
    )

    elapsed = time.time() - start_time

    phones = results.phones if hasattr(results, 'phones') else []
    emails = results.emails if hasattr(results, 'emails') else []
    stats = results.stats if hasattr(results, 'stats') else {}
    errors = results.errors if hasattr(results, 'errors') else []

    print(f"\nPhase 2 completed in {elapsed:.1f}s")
    print(f"\n[STATS]:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print(f"\n[EMAILS FOUND ({len(emails)})]:")
    for email in emails[:10]:
        if hasattr(email, 'email'):
            print(f"  - {email.email} ({email.source})")
        else:
            print(f"  - {email}")
    if len(emails) > 10:
        print(f"  ... and {len(emails) - 10} more")

    print(f"\n[PHONES FOUND ({len(phones)})]:")
    for phone in phones[:10]:
        if hasattr(phone, 'number'):
            print(f"  - {phone.number} ({phone.source})")
        else:
            print(f"  - {phone}")
    if len(phones) > 10:
        print(f"  ... and {len(phones) - 10} more")

    if errors:
        print(f"\n[ERRORS ({len(errors)})]:")
        for err in errors[:3]:
            print(f"  - {str(err)[:80]}...")

    return {
        'emails': emails,
        'phones': phones,
        'elapsed': elapsed
    }


def evaluate_results(target_name: str, profiles_tested: int, emails: list, phones: list) -> dict:
    """Evaluate if results meet success criteria."""
    required_emails = profiles_tested
    required_phones = profiles_tested

    found_emails = len(emails)
    found_phones = len(phones)

    email_pass = found_emails >= required_emails
    phone_pass = found_phones >= required_phones
    overall_pass = email_pass and phone_pass

    return {
        'target': target_name,
        'profiles_tested': profiles_tested,
        'emails_found': found_emails,
        'emails_required': required_emails,
        'email_pass': email_pass,
        'phones_found': found_phones,
        'phones_required': required_phones,
        'phone_pass': phone_pass,
        'overall_pass': overall_pass
    }


def print_evaluation_report(evaluations: list, cycle_num: int):
    """Print formatted evaluation report."""
    print("\n" + "="*65)
    print(f"|  CYCLE {cycle_num} EVALUATION REPORT" + " "*36 + "|")
    print("+" + "="*63 + "+")

    for eval_item in evaluations:
        status = "[PASS]" if eval_item['overall_pass'] else "[FAIL]"
        print(f"|  Target: {eval_item['target']:<50} |")
        print(f"|  Accounts tested: {eval_item['profiles_tested']:<45} |")
        print(f"|  Emails: {eval_item['emails_found']} (need {eval_item['emails_required']})" + " "*40 + "|")
        print(f"|  Phones: {eval_item['phones_found']} (need {eval_item['phones_required']})" + " "*40 + "|")
        print(f"|  Status: {status:<53} |")
        print("+" + "="*63 + "+")

    all_pass = all(e['overall_pass'] for e in evaluations)
    overall_status = "[SUCCESS]" if all_pass else "[NEEDS IMPROVEMENT]"
    print(f"|  OVERALL: {overall_status:<52} |")
    print("+" + "="*63 + "+")

    return all_pass


def main():
    """Main entry point."""
    print("\n" + "#"*65)
    print("#  IBP PHASE 2 TESTING - CYCLE 2                                #")
    print("#"*65)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nTest Targets:")
    for i, t in enumerate(TEST_TARGETS, 1):
        print(f"  {i}. {t['name']}")

    evaluations = []

    for target in TEST_TARGETS:
        target_name = target['name']
        photo_path = target.get('photo')
        profiles = target['profiles']

        try:
            results = run_phase2_search(profiles, target_name, photo_path)

            evaluation = evaluate_results(
                target_name,
                len(profiles),
                results['emails'],
                results['phones']
            )
            evaluations.append(evaluation)

        except Exception as e:
            print(f"\n[X] Error testing {target_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            evaluations.append({
                'target': target_name,
                'profiles_tested': len(profiles),
                'emails_found': 0,
                'emails_required': len(profiles),
                'email_pass': False,
                'phones_found': 0,
                'phones_required': len(profiles),
                'phone_pass': False,
                'overall_pass': False
            })

    all_pass = print_evaluation_report(evaluations, 2)

    if all_pass:
        print("\n" + "#"*65)
        print("#  ALL TESTS PASSING - CYCLE 2 SUCCESS                         #")
        print("#"*65)
        return 0
    else:
        print("\n" + "#"*65)
        print("#  TESTS FAILED - NEEDS MORE IMPROVEMENT                       #")
        print("#"*65)

        print("\n[FAILURE ANALYSIS]:")
        for eval_item in evaluations:
            if not eval_item['overall_pass']:
                print(f"\n  Target: {eval_item['target']}")
                if not eval_item['email_pass']:
                    print(f"    - Emails: {eval_item['emails_found']}/{eval_item['emails_required']}")
                if not eval_item['phone_pass']:
                    print(f"    - Phones: {eval_item['phones_found']}/{eval_item['phones_required']}")

        return 1


if __name__ == "__main__":
    sys.exit(main())
