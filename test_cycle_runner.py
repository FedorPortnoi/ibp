"""
IBP Phase 2 Improvement Cycle Test Runner
==========================================
Tests per-profile email and phone discovery.
Success criteria: Each profile needs 1+ VERIFIED email AND 1+ phone.
"""

import sys
import os
import time
from datetime import datetime
from typing import List, Dict, Tuple

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add the app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test targets from the user's specification
TEST_TARGETS = [
    {
        "name": "Alyona Smirnova",
        "name_cyrillic": "Алёна Смирнова",
        "photo": r"C:\Users\fedor\ibp\alenka.jpg"
    },
    {
        "name": "Danya Mescheryakov",
        "name_cyrillic": "Даня Мещеряков",
        "photo": r"C:\Users\fedor\ibp\mesch.jpg"
    },
    {
        "name": "Angelina Pilyushina",
        "name_cyrillic": "Ангелина Пилюшина",
        "photo": r"C:\Users\fedor\ibp\gel.jpg"
    }
]


def run_phase1_search(target_name: str, photo_path: str = None) -> List[Dict]:
    """Run Phase 1 to find social media profiles."""
    from app.services.combined_search import CombinedSearchService

    print(f"\n{'='*60}")
    print(f"PHASE 1: Finding profiles for {target_name}")
    print(f"Photo: {photo_path if photo_path and os.path.exists(photo_path) else 'None/Missing'}")
    print(f"{'='*60}")

    start_time = time.time()

    try:
        service = CombinedSearchService()
        results = service.search(
            target_name=target_name,
            target_photo_path=photo_path if photo_path and os.path.exists(photo_path) else None
        )

        elapsed = time.time() - start_time

        # Extract profiles from results
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

        print(f"Phase 1 completed in {elapsed:.1f}s - Found {len(profile_dicts)} profiles")

        for i, p in enumerate(profile_dicts[:10]):
            print(f"  {i+1}. [{p.get('platform', '?')}] {p.get('username', '')}: {p.get('url', '')[:60]}")

        if len(profile_dicts) > 10:
            print(f"  ... and {len(profile_dicts) - 10} more")

        return profile_dicts

    except Exception as e:
        print(f"Phase 1 ERROR: {e}")
        import traceback
        traceback.print_exc()
        return []


def run_phase2_per_profile(profiles: List[Dict], target_name: str):
    """Run Phase 2 with PER-PROFILE tracking."""
    from app.services.phase2.per_profile_search import PerProfileSearchService

    print(f"\n{'='*60}")
    print(f"PHASE 2: Per-Profile Contact Discovery")
    print(f"Target: {target_name}")
    print(f"Processing {len(profiles)} profiles")
    print(f"{'='*60}")

    service = PerProfileSearchService()

    try:
        results = service.investigate_all_profiles(
            profiles=profiles,
            target_name=target_name,
            max_profiles=5
        )
        return results
    finally:
        service.close()


def format_results_table(target_name: str, results) -> Tuple[str, bool, Dict]:
    """Format results as table and determine pass/fail status."""
    lines = []
    lines.append(f"\nTarget: {target_name}")
    lines.append("┌" + "─"*25 + "┬" + "─"*20 + "┬" + "─"*20 + "┬" + "─"*8 + "┐")
    lines.append(f"│ {'Profile URL':<23} │ {'Verified Emails':<18} │ {'Phones':<18} │ {'Status':<6} │")
    lines.append("├" + "─"*25 + "┼" + "─"*20 + "┼" + "─"*20 + "┼" + "─"*8 + "┤")

    passing_count = 0
    total_verified_emails = 0
    total_phones = 0

    for profile_result in results.profile_results:
        # Truncate URL for display
        url = profile_result.profile_url
        display_url = url.split('/')[-1][:20] if '/' in url else url[:20]

        # Format emails
        email_count = len(profile_result.verified_emails)
        total_verified_emails += email_count
        if email_count > 0:
            methods = set(e.verification_method for e in profile_result.verified_emails)
            email_str = f"{email_count} ({', '.join(methods)[:12]})"
        else:
            email_str = "0"

        # Format phones
        phone_count = len(profile_result.phones)
        total_phones += phone_count
        if phone_count > 0:
            phone_str = f"{phone_count}"
        else:
            phone_str = "0"

        # Status
        is_complete = profile_result.is_complete
        status = "✓" if is_complete else "✗"
        if is_complete:
            passing_count += 1

        lines.append(f"│ {display_url:<23} │ {email_str:<18} │ {phone_str:<18} │ {status:<6} │")

    lines.append("└" + "─"*25 + "┴" + "─"*20 + "┴" + "─"*20 + "┴" + "─"*8 + "┘")

    target_pass = results.all_pass if hasattr(results, 'all_pass') else (passing_count == len(results.profile_results))
    status_str = "PASS" if target_pass else f"FAIL ({passing_count}/{len(results.profile_results)} profiles complete)"
    lines.append(f"Target Status: {status_str}")

    stats = {
        'total_profiles': len(results.profile_results),
        'passing_profiles': passing_count,
        'total_verified_emails': total_verified_emails,
        'total_phones': total_phones,
        'target_pass': target_pass,
        'time': results.total_time if hasattr(results, 'total_time') else 0
    }

    return '\n'.join(lines), target_pass, stats


def run_single_cycle(cycle_num: int) -> Tuple[bool, Dict]:
    """Run a single test cycle and return results."""
    print("\n" + "="*65)
    print(f"CYCLE {cycle_num}/10 STARTING at {datetime.now().strftime('%H:%M:%S')}")
    print("="*65)

    cycle_start = time.time()
    all_results = []
    all_stats = []

    for target in TEST_TARGETS:
        target_name = target['name']
        photo_path = target['photo']

        try:
            # Phase 1: Find profiles
            profiles = run_phase1_search(target_name, photo_path)

            if not profiles:
                print(f"\n[X] No profiles found for {target_name}")
                all_results.append(False)
                all_stats.append({
                    'target': target_name,
                    'total_profiles': 0,
                    'passing_profiles': 0,
                    'total_verified_emails': 0,
                    'total_phones': 0,
                    'target_pass': False,
                    'time': 0
                })
                continue

            # Phase 2: Per-profile contact discovery
            results = run_phase2_per_profile(profiles[:5], target_name)

            # Format and display results
            table, target_pass, stats = format_results_table(target_name, results)
            print(table)

            stats['target'] = target_name
            all_results.append(target_pass)
            all_stats.append(stats)

        except Exception as e:
            print(f"\n[X] Error testing {target_name}: {e}")
            import traceback
            traceback.print_exc()
            all_results.append(False)
            all_stats.append({
                'target': target_name,
                'total_profiles': 0,
                'passing_profiles': 0,
                'total_verified_emails': 0,
                'total_phones': 0,
                'target_pass': False,
                'error': str(e),
                'time': 0
            })

    cycle_time = time.time() - cycle_start
    all_pass = all(all_results)

    # Cycle summary
    print("\n" + "="*65)
    print(f"CYCLE {cycle_num}/10 COMPLETE")
    print("="*65)
    print(f"Total verified emails: {sum(s['total_verified_emails'] for s in all_stats)}")
    print(f"Total phones: {sum(s['total_phones'] for s in all_stats)}")
    print(f"Cycle time: {cycle_time:.1f}s")
    print(f"OVERALL STATUS: {'PASS' if all_pass else 'FAIL'}")
    print("="*65)

    return all_pass, {
        'cycle': cycle_num,
        'all_pass': all_pass,
        'stats': all_stats,
        'cycle_time': cycle_time
    }


def main():
    """Main entry point."""
    print("\n" + "#"*65)
    print("#  IBP PHASE 2 PER-PROFILE TEST RUNNER")
    print("#"*65)
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print("\nTest Targets:")
    for i, t in enumerate(TEST_TARGETS, 1):
        photo_ok = "✓" if os.path.exists(t['photo']) else "✗"
        print(f"  {i}. {t['name']} (photo: {photo_ok})")

    # Run single cycle for testing
    cycle_pass, cycle_results = run_single_cycle(1)

    return 0 if cycle_pass else 1


if __name__ == "__main__":
    sys.exit(main())
