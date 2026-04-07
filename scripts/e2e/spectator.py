"""
AGENT 2: SPECTATOR + ERROR CATCHER
====================================
Reads runner output. Classifies every issue.
Hunts for silent failures -- system returned 200 but data is wrong.
"""

import json
from pathlib import Path
from datetime import datetime

RUNS_DIR = Path(r"C:\Users\fedor\ibp\.e2e_test\runs")
CANDIDATES_FILE = Path(r"C:\Users\fedor\ibp\.e2e_test\e2e_candidates.json")
CAPABILITY_FILE = Path(r"C:\Users\fedor\ibp\.e2e_test\capability_report.json")
SPECTATOR_REPORT = Path(r"C:\Users\fedor\ibp\.e2e_test\spectator_report.json")


def load_standards():
    """Load what the system CAN find (from Phase 0 discovery)."""
    try:
        with open(CAPABILITY_FILE, encoding='utf-8') as f:
            cap = json.load(f)
        real_sources = [
            s for s, v in
            cap.get('probe_candidate', {}).get('sources_with_data', {}).items()
            if v == 'REAL'
        ]
        print(f"OK Standards loaded. REAL sources: {real_sources}")
        return real_sources
    except FileNotFoundError:
        print("WARN No capability report. Using minimum assumptions.")
        return ['COURTS', 'RISK_SCORE']


def classify_issue(msg, pct, candidate):
    """Classify pipeline issue: BUG / EXPECTED / DATA_ISSUE / TIMEOUT / INFO."""
    msg_lower = msg.lower()

    EXPECTED_PATTERNS = [
        'гувм мвд недоступен',
        'гувм мвд',
        'прекращён с июля 2023',
        'госуслуги',
        'росфинмониторинг',
        'геоблокировка',
        'сайт недоступен',
        'ok.ru: профили не найдены (демо)',
        'ok.ru: профили не найдены',
        'demo', 'демо',
        'getcontact', 'numbuster',
        'snusbase', 'dehashed',
        'search4faces',
        'api ключ не задан',
        'ключ не настроен',
    ]

    BUG_PATTERNS = [
        'traceback',
        'exception',
        'attributeerror',
        'keyerror',
        'valueerror',
        'typeerror',
        'syntaxerror',
        'internal server error',
        'database error',
        'sqlalchemy',
    ]

    for pattern in BUG_PATTERNS:
        if pattern in msg_lower:
            return {'type': 'BUG', 'severity': 'CRITICAL', 'msg': msg}

    for pattern in EXPECTED_PATTERNS:
        if pattern in msg_lower:
            return {'type': 'EXPECTED', 'severity': 'INFO', 'msg': msg}

    if 'timeout' in msg_lower or 'hang' in msg_lower:
        return {'type': 'TIMEOUT', 'severity': 'HIGH', 'msg': msg}

    if any(kw in msg_lower for kw in ['не найден', 'not found', 'записей не найдено', '0 результат']):
        return {'type': 'NO_DATA', 'severity': 'MEDIUM', 'msg': msg}

    if 'ошибка' in msg_lower or 'error' in msg_lower or 'failed' in msg_lower:
        return {'type': 'ERROR', 'severity': 'HIGH', 'msg': msg}

    return {'type': 'INFO', 'severity': 'LOW', 'msg': msg}


def detect_silent_failures(run_record, candidate, real_sources):
    """
    Silent failure = system returned 200 and 'complete'
    but critical data is missing that we know the system can find.
    """
    failures = []
    dossier = run_record.get('export_json', {}) or {}
    expected_risk = candidate.get('expected_risk', 'LOW')
    known_flags = candidate.get('known_flags', [])

    # The dossier uses nested structure
    risk_data = dossier.get('risk_assessment', {}) or {}
    risk_score = risk_data.get('risk_score', 0) or 0

    # Check 1: Risk score sanity
    if expected_risk == 'CRITICAL' and risk_score < 60:
        failures.append({
            'type': 'SILENT_FAIL', 'severity': 'CRITICAL',
            'field': 'risk_score',
            'expected': f'>=60 (candidate is {expected_risk})',
            'got': risk_score,
            'msg': f'CRITICAL candidate scored only {risk_score}/100',
        })
    elif expected_risk == 'HIGH' and risk_score < 40:
        failures.append({
            'type': 'SILENT_FAIL', 'severity': 'HIGH',
            'field': 'risk_score',
            'expected': f'>=40 (candidate is {expected_risk})',
            'got': risk_score,
            'msg': f'HIGH candidate scored only {risk_score}/100',
        })

    # Check 2: Courts (if known_flags mention criminal records)
    has_criminal = any(
        any(kw in f.lower() for kw in ['судим', 'приговор', 'уголовн', 'ст.', 'ук рф'])
        for f in known_flags
    )
    if has_criminal and 'COURTS' in real_sources:
        courts = dossier.get('court_records', [])
        if not courts:
            failures.append({
                'type': 'SILENT_FAIL', 'severity': 'CRITICAL',
                'field': 'court_records',
                'expected': 'Criminal records present',
                'got': 'EMPTY',
                'msg': 'Known criminal history but courts returned nothing',
            })

    # Check 3: FSSP
    has_fssp = any(
        any(kw in f.lower() for kw in ['фссп', 'долг', 'задолженн', 'млн', 'алимент'])
        for f in known_flags
    )
    if has_fssp:
        fssp = dossier.get('fssp_records', [])
        if not fssp:
            failures.append({
                'type': 'SILENT_FAIL', 'severity': 'HIGH',
                'field': 'fssp_records',
                'expected': 'FSSP records (known debts)',
                'got': 'EMPTY',
                'msg': 'Known FSSP debts but nothing found',
            })

    # Check 4: VK demo data leak
    vk_profiles = dossier.get('social_media_profiles', [])
    if vk_profiles and isinstance(vk_profiles, list):
        for p in vk_profiles:
            pid = str(p.get('vk_id', p.get('platform_id', '')))
            if pid in ('123456789', '987654321', '111111111', '000000001'):
                failures.append({
                    'type': 'DEMO_DATA_LEAK', 'severity': 'MEDIUM',
                    'field': 'social_media_profiles',
                    'expected': 'Real VK profiles',
                    'got': f'Demo profile ID {pid}',
                    'msg': 'VK returned demo/fake profiles in production',
                })

    # Check 5: No INN - must handle gracefully
    if not candidate.get('inn'):
        if run_record.get('final_status') in ('PIPELINE_ERROR', 'EXCEPTION'):
            failures.append({
                'type': 'BUG', 'severity': 'CRITICAL',
                'field': 'inn_handling',
                'expected': 'Graceful handling of missing INN',
                'got': run_record.get('final_status'),
                'msg': 'System crashed when INN is empty',
            })

    # Check 6: Duration
    duration = run_record.get('duration_seconds', 0)
    if duration > 300 and run_record.get('final_status') == 'COMPLETE':
        failures.append({
            'type': 'PERFORMANCE', 'severity': 'MEDIUM',
            'field': 'duration',
            'expected': '<300 seconds',
            'got': f'{duration:.0f} seconds',
            'msg': f'Pipeline too slow: {duration:.0f}s',
        })

    return failures


def analyze_run(run_record, candidate, real_sources):
    name = candidate['full_name']
    cid = candidate['id']
    print(f"\n{'_'*60}")
    print(f"SPECTATOR: Candidate {cid} -- {name}")
    print(f"{'_'*60}")

    analysis = {
        'candidate_id': cid,
        'full_name': name,
        'final_status': run_record.get('final_status'),
        'duration': run_record.get('duration_seconds'),
        'classified_issues': [],
        'silent_failures': [],
        'summary': {},
    }

    bugs = []
    expected_issues = []
    no_data = []
    timeouts = []
    errors_list = []

    for entry in run_record.get('progress_log', []):
        classified = classify_issue(entry['msg'], entry['pct'], candidate)
        classified['pct'] = entry['pct']
        analysis['classified_issues'].append(classified)

        if classified['type'] == 'BUG':
            bugs.append(classified)
        elif classified['type'] == 'EXPECTED':
            expected_issues.append(classified)
        elif classified['type'] == 'NO_DATA':
            no_data.append(classified)
        elif classified['type'] == 'TIMEOUT':
            timeouts.append(classified)
        elif classified['type'] == 'ERROR':
            errors_list.append(classified)

    # Also classify explicit errors from runner
    for err in run_record.get('errors', []):
        classified = classify_issue(err, -1, candidate)
        if classified['type'] == 'BUG':
            bugs.append(classified)
        else:
            errors_list.append(classified)

    # Detect silent failures
    silent = detect_silent_failures(run_record, candidate, real_sources)
    analysis['silent_failures'] = silent

    analysis['summary'] = {
        'bugs': len(bugs),
        'errors': len(errors_list),
        'expected_limitations': len(expected_issues),
        'no_data_events': len(no_data),
        'timeouts': len(timeouts),
        'silent_failures': len(silent),
        'critical_issues': len([i for i in silent if i.get('severity') == 'CRITICAL']),
    }

    if bugs:
        print(f"  BUGS ({len(bugs)}):")
        for b in bugs[:5]:
            print(f"     {b['msg'][:80]}")
    if silent:
        print(f"  SILENT FAILURES ({len(silent)}):")
        for s in silent:
            print(f"     [{s['severity']}] {s['msg'][:80]}")
    if errors_list:
        print(f"  ERRORS ({len(errors_list)}):")
        for e in errors_list[:3]:
            print(f"     {e['msg'][:80]}")
    if expected_issues:
        print(f"  Expected limitations ({len(expected_issues)}) -- known, not bugs")
    if not bugs and not silent and not errors_list:
        print(f"  OK No bugs or silent failures detected")

    return analysis


if __name__ == '__main__':
    print("=" * 70)
    print("AGENT 2: SPECTATOR + ERROR CATCHER")
    print("=" * 70)

    real_sources = load_standards()

    with open(CANDIDATES_FILE, encoding='utf-8') as f:
        candidates = {c['id']: c for c in json.load(f)}

    all_analyses = []
    run_files = sorted(RUNS_DIR.glob("run_*.json"))

    if not run_files:
        print("FAIL No run files found. Run candidate_runner.py first.")
        exit(1)

    for run_file in run_files:
        if run_file.name == 'run_summary.json':
            continue
        with open(run_file, encoding='utf-8') as f:
            run_record = json.load(f)

        cid = run_record['candidate_id']
        candidate = candidates.get(cid, {})
        if not candidate:
            print(f"WARN No candidate data for ID {cid}")
            continue

        analysis = analyze_run(run_record, candidate, real_sources)
        all_analyses.append(analysis)

    # Summary
    print("\n" + "=" * 70)
    print("SPECTATOR SUMMARY")
    print("=" * 70)
    total_bugs = sum(a['summary']['bugs'] for a in all_analyses)
    total_silent = sum(a['summary']['silent_failures'] for a in all_analyses)
    total_critical = sum(a['summary']['critical_issues'] for a in all_analyses)

    for a in all_analyses:
        s = a['summary']
        icon = 'OK' if s['bugs'] == 0 and s['silent_failures'] == 0 else 'FAIL'
        print(f"{icon} [{a['candidate_id']:02d}] {a['full_name'][:35]:<35} "
              f"B:{s['bugs']} E:{s['errors']} SF:{s['silent_failures']} C:{s['critical_issues']}")

    print(f"\nTOTAL: {total_bugs} bugs, {total_silent} silent failures, "
          f"{total_critical} critical issues")

    report = {
        'timestamp': datetime.utcnow().isoformat(),
        'analyses': all_analyses,
        'totals': {
            'bugs': total_bugs,
            'silent_failures': total_silent,
            'critical': total_critical,
        },
    }
    with open(SPECTATOR_REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nSpectator report: {SPECTATOR_REPORT}")
