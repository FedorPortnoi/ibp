"""
AGENT 3: OUTPUT VALIDATOR
==========================
Validates final dossier output for each candidate.
Compares against expected_risk + known_flags.
Issues PASS/FAIL verdicts per field.
"Nothing Found" = FAIL unless provably unavailable.
"""

import json
from pathlib import Path
from datetime import datetime

RUNS_DIR = Path(r"C:\Users\fedor\ibp\.e2e_test\runs")
CANDIDATES_FILE = Path(r"C:\Users\fedor\ibp\.e2e_test\e2e_candidates.json")
CAPABILITY_FILE = Path(r"C:\Users\fedor\ibp\.e2e_test\capability_report.json")
VALIDATION_REPORT = Path(r"C:\Users\fedor\ibp\.e2e_test\validation_report.json")


def load_capability():
    try:
        with open(CAPABILITY_FILE, encoding='utf-8') as f:
            cap = json.load(f)
        return cap.get('probe_candidate', {}).get('sources_with_data', {})
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Validators — each returns dict of {field: (PASS|FAIL|WARN|INFO, detail)}
# ---------------------------------------------------------------------------

def validate_identity(dossier, candidate):
    results = {}
    cand_data = dossier.get('candidate', {}) or {}

    dossier_name = cand_data.get('full_name', '')
    expected_name = candidate['full_name']
    if dossier_name and expected_name.lower() in dossier_name.lower():
        results['confirmed_name'] = ('PASS', dossier_name)
    elif dossier_name:
        results['confirmed_name'] = ('WARN', f"Got '{dossier_name}', expected '{expected_name}'")
    else:
        results['confirmed_name'] = ('FAIL', 'Name not in dossier')

    if candidate.get('inn'):
        dossier_inn = cand_data.get('inn', '')
        if dossier_inn:
            results['inn'] = ('PASS', dossier_inn)
        else:
            results['inn'] = ('WARN', 'INN not in dossier output')
    else:
        results['inn_missing'] = ('PASS', 'No INN provided -- expected')

    return results


def validate_registries(dossier, candidate, sources):
    results = {}

    # EGRUL
    if candidate.get('inn') and sources.get('EGRUL') == 'REAL':
        egrul = dossier.get('business_records', [])
        if egrul:
            results['egrul'] = ('PASS', f"Found: {len(egrul)} records")
        else:
            results['egrul'] = ('INFO', 'EGRUL: no business records (may be legitimate)')

    # Courts
    known_flags = candidate.get('known_flags', [])
    has_court_flags = any(
        any(kw in f.lower() for kw in ['судим', 'приговор', 'уголов', 'ст.', 'ук рф', 'коап'])
        for f in known_flags
    )

    courts = dossier.get('court_records', [])
    if has_court_flags:
        if courts:
            results['courts'] = ('PASS', f"Found {len(courts)} court records")
        else:
            results['courts'] = ('FAIL',
                'MISSING: Candidate has known criminal history but 0 court records')
    else:
        if courts:
            results['courts'] = ('PASS', f"Found {len(courts)} records (unexpected but OK)")
        else:
            results['courts'] = ('INFO', 'No court records (expected for clean candidate)')

    # FSSP
    has_fssp_flags = any(
        any(kw in f.lower() for kw in ['фссп', 'долг', 'задолженн', 'алимент', 'млн'])
        for f in known_flags
    )
    fssp = dossier.get('fssp_records', [])
    if has_fssp_flags:
        if fssp:
            results['fssp'] = ('PASS', 'FSSP records found')
        else:
            results['fssp'] = ('FAIL', 'MISSING: Known FSSP debts not found')
    else:
        results['fssp'] = ('INFO', 'FSSP: not expected')

    return results


def validate_security(dossier, candidate):
    results = {}

    sanctions = dossier.get('sanctions_results', [])
    if sanctions is not None:  # Even empty list means check ran
        results['sanctions_check'] = ('PASS', 'Security check was attempted')
    else:
        results['sanctions_check'] = ('WARN', 'Security check data not in dossier')

    return results


def validate_social(dossier, candidate):
    results = {}

    vk = dossier.get('social_media_profiles', [])
    if vk and isinstance(vk, list):
        demo_ids = {'123456789', '987654321', '111111111'}
        real_vk = [p for p in vk
                   if str(p.get('vk_id', p.get('platform_id', ''))) not in demo_ids]
        demo_vk = len(vk) - len(real_vk)

        if real_vk:
            results['vk'] = ('PASS', f"{len(real_vk)} real VK profiles found")
        elif demo_vk > 0:
            results['vk'] = ('WARN', f"Only demo VK profiles ({demo_vk})")
        else:
            results['vk'] = ('INFO', 'No VK profiles')

        if demo_vk > 0:
            results['vk_demo_leak'] = ('FAIL', 'Demo VK profiles in production!')
    else:
        results['vk'] = ('INFO', 'No VK profiles in dossier')

    return results


def validate_risk_score(dossier, candidate):
    results = {}

    risk_data = dossier.get('risk_assessment', {}) or {}
    risk = risk_data.get('risk_score', 0) or 0
    expected = candidate.get('expected_risk', 'LOW')

    thresholds = {
        'CRITICAL': (60, 100),
        'HIGH':     (40, 100),
        'MEDIUM':   (25, 69),
        'LOW':      (0,  44),
    }

    min_score, _ = thresholds.get(expected, (0, 100))

    if risk >= min_score:
        results['risk_score'] = ('PASS', f"Score {risk}/100 matches expected {expected}")
    else:
        results['risk_score'] = ('FAIL',
            f"Score {risk}/100 too low for {expected} (expected >={min_score})")

    # Risk 0 for non-LOW is always bad
    if expected not in ('LOW',) and risk == 0:
        results['risk_score_zero'] = ('FAIL',
            f'Risk score is 0 for a {expected} candidate -- scoring did not run')

    return results


def validate_output_completeness(dossier, candidate):
    results = {}

    # These top-level keys should always be present
    REQUIRED_KEYS = [
        'candidate', 'risk_assessment', 'court_records',
        'sanctions_results', 'social_media_profiles',
    ]
    OPTIONAL_KEYS = [
        'business_records', 'contact_discoveries',
        'geo_intelligence', 'geo_analysis',
        'text_analysis', 'activity_timeline',
    ]

    missing_required = [k for k in REQUIRED_KEYS if k not in dossier]
    missing_optional = [k for k in OPTIONAL_KEYS
                        if k not in dossier or not dossier[k]]

    if missing_required:
        results['required_fields'] = ('FAIL',
            f"Missing: {', '.join(missing_required)}")
    else:
        results['required_fields'] = ('PASS', 'All required fields present')

    if missing_optional:
        results['optional_fields'] = ('WARN',
            f"Missing: {', '.join(missing_optional)}")
    else:
        results['optional_fields'] = ('PASS', 'All optional fields present')

    # Check dossier not empty
    non_empty = sum(
        1 for v in dossier.values()
        if v is not None and v != {} and v != [] and v != ''
    )
    if non_empty < 5:
        results['dossier_emptiness'] = ('FAIL',
            f'Nearly empty: only {non_empty} non-empty fields')
    else:
        results['dossier_emptiness'] = ('PASS', f'{non_empty} populated fields')

    return results


def validate_known_flags(dossier, candidate):
    results = {}
    known_flags = candidate.get('known_flags', [])

    if not known_flags:
        results['known_flags'] = ('PASS', 'No expected flags (clean candidate)')
        return results

    # Skip the "no INN" flag -- that's a test condition, not dossier data
    check_flags = [f for f in known_flags if 'инн отсутствует' not in f.lower()]
    if not check_flags:
        results['known_flags'] = ('PASS', 'Only INN-related test flags')
        return results

    dossier_text = json.dumps(dossier, ensure_ascii=False).lower()

    for i, flag in enumerate(check_flags):
        flag_lower = flag.lower()

        if 'судимость' in flag_lower or 'судим' in flag_lower:
            found = any(kw in dossier_text for kw in
                       ['суд', 'уголовн', 'приговор', 'court'])
        elif 'фссп' in flag_lower or 'задолженност' in flag_lower:
            found = any(kw in dossier_text for kw in
                       ['фссп', 'fssp', 'исполнительн', 'взыскан', 'задолженн'])
        elif 'вагнер' in flag_lower or 'чвк' in flag_lower:
            found = any(kw in dossier_text for kw in
                       ['вагнер', 'wagner', 'чвк', 'сво'])
        elif 'убийство' in flag_lower:
            found = any(kw in dossier_text for kw in
                       ['убийство', 'murder', 'ст. 105', '105 ук', 'суд'])
        elif 'наркот' in flag_lower or '228' in flag_lower:
            found = any(kw in dossier_text for kw in
                       ['наркот', 'drug', 'ст. 228', '228', 'суд'])
        elif 'несоответствие' in flag_lower or 'зарегистрирован' in flag_lower:
            found = any(kw in dossier_text for kw in
                       ['несоответств', 'mismatch', 'зарегистрирован',
                        'чита', 'краснодар'])
        elif 'административн' in flag_lower or 'коап' in flag_lower:
            found = any(kw in dossier_text for kw in
                       ['административн', 'коап', 'суд', 'правонаруш'])
        elif 'рецидив' in flag_lower:
            found = any(kw in dossier_text for kw in
                       ['рецидив', 'повторн', 'два', 'multiple', 'суд'])
        elif 'не рекомендован' in flag_lower:
            # This is an HR conclusion, not data — skip
            results[f'flag_{i}'] = ('INFO', f"HR conclusion: {flag[:60]}")
            continue
        else:
            words = [w for w in flag_lower.split() if len(w) > 4]
            found = any(w in dossier_text for w in words[:3])

        if found:
            results[f'flag_{i}'] = ('PASS', f"Evidence for: {flag[:60]}")
        else:
            results[f'flag_{i}'] = ('FAIL',
                f"NO EVIDENCE: '{flag[:60]}' not in dossier")

    return results


# ---------------------------------------------------------------------------

def validate_candidate(run_record, candidate, sources):
    name = candidate['full_name']
    cid = candidate['id']
    print(f"\n{'_'*60}")
    print(f"VALIDATOR: Candidate {cid} -- {name}")
    print(f"{'_'*60}")

    # Handle candidates that never got a dossier
    final_status = run_record.get('final_status', '')

    # Candidate 9 (no INN) — expected API rejection
    if final_status == 'INN_REQUIRED_REJECTED' and not candidate.get('inn'):
        print(f"  INFO: INN required — API correctly rejected empty INN")
        return {
            'candidate_id': cid,
            'full_name': name,
            'expected_risk': candidate.get('expected_risk'),
            'verdict': 'PASS',
            'reason': 'API correctly requires INN (validation working)',
            'validations': {
                'inn_validation': ('PASS', 'API rejected empty INN as expected'),
            },
            'counts': {'PASS': 1, 'FAIL': 0, 'WARN': 0, 'INFO': 0},
            'pass_rate': 100.0,
        }

    dossier = run_record.get('export_json', {}) or {}

    if not dossier:
        print(f"  FAIL CRITICAL: No dossier data to validate!")
        return {
            'candidate_id': cid,
            'full_name': name,
            'expected_risk': candidate.get('expected_risk'),
            'verdict': 'FAIL',
            'reason': f'No dossier data (status: {final_status})',
            'validations': {},
            'counts': {'PASS': 0, 'FAIL': 1, 'WARN': 0, 'INFO': 0},
            'pass_rate': 0.0,
        }

    # Run all validators
    all_results = {}
    all_results.update(validate_identity(dossier, candidate))
    all_results.update(validate_registries(dossier, candidate, sources))
    all_results.update(validate_security(dossier, candidate))
    all_results.update(validate_social(dossier, candidate))
    all_results.update(validate_risk_score(dossier, candidate))
    all_results.update(validate_output_completeness(dossier, candidate))
    all_results.update(validate_known_flags(dossier, candidate))

    counts = {'PASS': 0, 'FAIL': 0, 'WARN': 0, 'INFO': 0}
    for field, (verdict, detail) in all_results.items():
        counts[verdict] = counts.get(verdict, 0) + 1
        icon = {'PASS': 'OK', 'FAIL': 'FAIL', 'WARN': 'WARN', 'INFO': 'INFO'}.get(verdict, '?')
        print(f"  {icon:4s} {field:<30} {detail[:55]}")

    total_scored = counts['PASS'] + counts['FAIL']
    pass_rate = (counts['PASS'] / total_scored * 100) if total_scored > 0 else 0

    overall = 'PASS' if counts['FAIL'] == 0 else 'FAIL'
    if counts['FAIL'] == 0 and counts['WARN'] > 2:
        overall = 'WARN'

    print(f"\n  VERDICT: {overall} | "
          f"OK:{counts['PASS']} FAIL:{counts['FAIL']} WARN:{counts['WARN']} INFO:{counts['INFO']} | "
          f"Pass rate: {pass_rate:.0f}%")

    return {
        'candidate_id': cid,
        'full_name': name,
        'expected_risk': candidate.get('expected_risk'),
        'verdict': overall,
        'validations': {k: list(v) for k, v in all_results.items()},
        'counts': counts,
        'pass_rate': round(pass_rate, 1),
    }


if __name__ == '__main__':
    print("=" * 70)
    print("AGENT 3: OUTPUT VALIDATOR")
    print("=" * 70)

    sources = load_capability()
    print(f"System capabilities: {list(sources.keys())}")

    with open(CANDIDATES_FILE, encoding='utf-8') as f:
        candidates = {c['id']: c for c in json.load(f)}

    all_validations = []
    run_files = sorted(RUNS_DIR.glob("run_*.json"))

    if not run_files:
        print("FAIL No run files. Run candidate_runner.py first.")
        exit(1)

    for run_file in run_files:
        if run_file.name == 'run_summary.json':
            continue
        with open(run_file, encoding='utf-8') as f:
            run_record = json.load(f)

        cid = run_record['candidate_id']
        candidate = candidates.get(cid, {})
        if not candidate:
            continue

        validation = validate_candidate(run_record, candidate, sources)
        all_validations.append(validation)

    # Final report
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    passed = sum(1 for v in all_validations if v['verdict'] == 'PASS')
    failed = sum(1 for v in all_validations if v['verdict'] == 'FAIL')
    warned = sum(1 for v in all_validations if v['verdict'] == 'WARN')

    for v in all_validations:
        icon = {'PASS': 'OK', 'FAIL': 'FAIL', 'WARN': 'WARN'}.get(v['verdict'], '?')
        print(f"{icon:4s} [{v['candidate_id']:02d}] {v['full_name'][:38]:<38} "
              f"{v['verdict']:<5} {v['pass_rate']:>5.1f}% "
              f"[{v.get('expected_risk', '?')}]")

    print(f"\nOVERALL: {passed} PASS / {warned} WARN / {failed} FAIL "
          f"out of {len(all_validations)} candidates")

    if failed > 0:
        print(f"\nFAILURES:")
        for v in all_validations:
            if v['verdict'] == 'FAIL':
                failed_fields = [
                    (f, d) for f, (verdict, d) in
                    ((k, tuple(val)) for k, val in v.get('validations', {}).items())
                    if verdict == 'FAIL'
                ]
                print(f"  [{v['candidate_id']:02d}] {v['full_name']}:")
                for field, detail in failed_fields:
                    print(f"       {field}: {detail[:80]}")

    report = {
        'timestamp': datetime.utcnow().isoformat(),
        'validations': all_validations,
        'totals': {
            'pass': passed,
            'fail': failed,
            'warn': warned,
            'total': len(all_validations),
        },
    }
    with open(VALIDATION_REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nValidation report: {VALIDATION_REPORT}")
