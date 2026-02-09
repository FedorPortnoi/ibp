"""
Phase 3 End-to-End Test
=======================
Tests Phase 3 deep investigation flow:
1. Create investigation at phase_2_complete status
2. Start Phase 3 investigation via API
3. Poll for progress
4. Verify results page renders
5. Verify DB records saved
"""

import sys
import io
import os
import time
import json
import uuid
import requests

# UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://127.0.0.1:5000"

# Test targets
TARGETS = [
    {"name": "Кузнецов Дмитрий", "desc": "common name, high chance of business records"},
    {"name": "Козлова Алёна", "desc": "Ё handling test"},
    {"name": "Новиков Фёдор", "desc": "another Ё handling test"},
]


def create_test_investigation(name: str) -> str:
    """Create a test investigation at phase_2_complete status."""
    from app import create_app, db
    from app.models import Investigation, SocialProfile

    app = create_app()
    with app.app_context():
        inv_id = uuid.uuid4().hex[:16]
        inv = Investigation(
            id=inv_id,
            input_name=name,
            status='phase_2_complete',
            confirmed_platform='vk',
            confirmed_username='test_user',
        )
        inv.discovered_emails = [{'email': 'test@mail.ru', 'source': 'demo', 'verification': 'pattern'}]
        inv.discovered_phones = [{'number': '+79001234567', 'source': 'demo', 'confidence': 'low'}]
        db.session.add(inv)

        # Add a confirmed profile
        parts = name.split()
        profile = SocialProfile(
            investigation_id=inv_id,
            platform='vk',
            platform_id='12345',
            username='test_user',
            first_name=parts[1] if len(parts) > 1 else name,
            last_name=parts[0] if len(parts) > 0 else '',
            display_name=name,
            is_confirmed=True,
            bio='Тестовый профиль из Москвы',
        )
        db.session.add(profile)
        db.session.commit()
        print(f"  Created investigation {inv_id} for {name}")
        return inv_id


def test_phase3_api(inv_id: str, name: str) -> dict:
    """Test Phase 3 API flow: start → poll → results."""
    results = {
        'name': name,
        'inv_id': inv_id,
        'success': False,
        'business_records': 0,
        'court_cases': 0,
        'enforcement_proceedings': 0,
        'risk_indicators': 0,
        'manual_links': 0,
        'errors': [],
        'time': 0,
    }

    # Step 1: Start Phase 3
    print(f"\n  [{name}] Starting Phase 3...")
    try:
        resp = requests.post(f"{BASE_URL}/phase3/api/buratino/start/{inv_id}",
                           headers={'Content-Type': 'application/json'}, timeout=10)
        data = resp.json()
        if not data.get('success'):
            results['errors'].append(f"Start failed: {data.get('error')}")
            return results
        task_id = data['task_id']
        print(f"  [{name}] Task started: {task_id}")
    except Exception as e:
        results['errors'].append(f"Start error: {e}")
        return results

    # Step 2: Poll for progress
    start_time = time.time()
    max_wait = 120  # 2 minutes max
    last_step = ""

    while time.time() - start_time < max_wait:
        try:
            resp = requests.get(f"{BASE_URL}/phase3/progress/{task_id}", timeout=10)
            progress = resp.json()

            step = progress.get('current_step', '')
            pct = progress.get('percent_complete', 0)
            if step != last_step:
                print(f"  [{name}] [{pct}%] {step}")
                last_step = step

            if progress.get('is_complete'):
                if progress.get('error'):
                    results['errors'].append(f"Task error: {progress['error']}")
                    return results
                break
        except Exception as e:
            results['errors'].append(f"Poll error: {e}")

        time.sleep(2)

    elapsed = time.time() - start_time
    results['time'] = round(elapsed, 1)

    if elapsed >= max_wait:
        results['errors'].append("Timeout waiting for completion")
        return results

    # Step 3: Check results
    try:
        resp = requests.get(f"{BASE_URL}/phase3/api/results/{task_id}", timeout=10)
        data = resp.json()
        if data.get('status') == 'success':
            r = data.get('results', {})
            stats = r.get('stats', {})
            results['business_records'] = stats.get('business_records_found', 0)
            results['court_cases'] = stats.get('court_cases_found', 0)
            results['enforcement_proceedings'] = stats.get('enforcement_proceedings_found', 0)
            results['risk_indicators'] = stats.get('risk_indicators_found', 0)
            results['manual_links'] = len(r.get('manual_search_links', []))
            results['success'] = True
            print(f"  [{name}] Results: {results['business_records']} biz, {results['court_cases']} court, {results['risk_indicators']} risks in {elapsed:.1f}s")
        else:
            results['errors'].append(f"Results error: {data.get('error')}")
    except Exception as e:
        results['errors'].append(f"Results fetch error: {e}")

    # Step 4: Check results page renders
    try:
        resp = requests.get(f"{BASE_URL}/phase3/buratino/results/{inv_id}", timeout=10)
        if resp.status_code == 200:
            if 'Business Records' in resp.text or 'EGRUL' in resp.text:
                print(f"  [{name}] Results page renders OK")
            else:
                results['errors'].append("Results page missing expected content")
        else:
            results['errors'].append(f"Results page status: {resp.status_code}")
    except Exception as e:
        results['errors'].append(f"Results page error: {e}")

    # Step 5: Check DB records
    from app import create_app, db
    app = create_app()
    with app.app_context():
        from app.models import Investigation, BusinessRecord, CourtRecord
        inv = Investigation.query.get(inv_id)
        if inv:
            if inv.status == 'phase_3_complete':
                print(f"  [{name}] DB status: phase_3_complete ✓")
            else:
                results['errors'].append(f"DB status: {inv.status} (expected phase_3_complete)")

            db_biz = BusinessRecord.query.filter_by(investigation_id=inv_id).count()
            db_court = CourtRecord.query.filter_by(investigation_id=inv_id).count()
            print(f"  [{name}] DB records: {db_biz} business, {db_court} court")

            # Check risk indicators stored
            risk = inv.risk_indicators
            print(f"  [{name}] Risk indicators stored: {len(risk)}")

            # Check manual links stored
            links = inv.additional_findings
            print(f"  [{name}] Manual links stored: {len(links)}")

    return results


def test_phase3_loading_page(inv_id: str) -> bool:
    """Test that the Phase 3 loading page renders."""
    try:
        resp = requests.get(f"{BASE_URL}/phase3/buratino/{inv_id}", timeout=10)
        if resp.status_code == 200 and 'Deep Investigation' in resp.text:
            return True
    except:
        pass
    return False


def test_dashboard_shows_phase3(inv_id: str) -> bool:
    """Test that dashboard shows Phase 3 status."""
    try:
        resp = requests.get(f"{BASE_URL}/investigations", timeout=10)
        if resp.status_code == 200 and 'Phase 3 Done' in resp.text:
            return True
    except:
        pass
    return False


def main():
    print("=" * 60)
    print("PHASE 3 END-TO-END TEST")
    print("=" * 60)

    all_results = []

    for target in TARGETS:
        name = target['name']
        print(f"\n{'=' * 40}")
        print(f"TARGET: {name} ({target['desc']})")
        print(f"{'=' * 40}")

        # Create test investigation
        inv_id = create_test_investigation(name)

        # Test loading page
        loading_ok = test_phase3_loading_page(inv_id)
        print(f"  Loading page: {'OK' if loading_ok else 'FAIL'}")

        # Run Phase 3
        result = test_phase3_api(inv_id, name)
        all_results.append(result)

    # Check dashboard
    if all_results:
        dashboard_ok = test_dashboard_shows_phase3(all_results[0]['inv_id'])
        print(f"\nDashboard shows Phase 3: {'OK' if dashboard_ok else 'FAIL'}")

    # Summary
    print(f"\n{'=' * 60}")
    print("PHASE 3 E2E TEST SUMMARY")
    print(f"{'=' * 60}")

    for r in all_results:
        status = "PASS" if r['success'] else "FAIL"
        print(f"  {r['name']}: {status} | Biz={r['business_records']} Court={r['court_cases']} FSSP={r['enforcement_proceedings']} Risks={r['risk_indicators']} Links={r['manual_links']} | {r['time']}s")
        if r['errors']:
            for err in r['errors']:
                print(f"    ERROR: {err}")

    passed = sum(1 for r in all_results if r['success'])
    total = len(all_results)
    print(f"\n  TOTAL: {passed}/{total} passed")
    print(f"{'=' * 60}")

    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
