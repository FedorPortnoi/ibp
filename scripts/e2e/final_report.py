"""
FINAL REPORT: Aggregates all agent outputs into one report.
Generates prioritized fix recommendations.
"""

import json
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path(r"C:\Users\fedor\ibp\.e2e_test")
FINAL_REPORT = OUTPUT_DIR / "FINAL_E2E_REPORT.json"
FINAL_REPORT_MD = OUTPUT_DIR / "FINAL_E2E_REPORT.md"


def generate_final_report():
    reports = {}
    for filename in ['capability_report.json', 'spectator_report.json',
                     'validation_report.json']:
        path = OUTPUT_DIR / filename
        if path.exists():
            with open(path, encoding='utf-8') as f:
                reports[filename.replace('.json', '')] = json.load(f)
        else:
            print(f"WARN Missing: {filename}")

    run_summary_path = OUTPUT_DIR / 'runs' / 'run_summary.json'
    if run_summary_path.exists():
        with open(run_summary_path, encoding='utf-8') as f:
            reports['run_summary'] = json.load(f)

    validation = reports.get('validation_report', {})
    spectator = reports.get('spectator_report', {})

    validations = validation.get('validations', [])
    total_bugs = spectator.get('totals', {}).get('bugs', 0)
    total_silent = spectator.get('totals', {}).get('silent_failures', 0)
    val_totals = validation.get('totals', {})

    # Collect all FAILs
    all_failures = []
    for v in validations:
        for field, val in (v.get('validations') or {}).items():
            verdict, detail = val[0], val[1] if len(val) > 1 else ''
            if verdict == 'FAIL':
                all_failures.append({
                    'candidate': v['full_name'],
                    'candidate_id': v['candidate_id'],
                    'field': field,
                    'detail': detail,
                    'priority': 'CRITICAL' if any(kw in detail.lower()
                        for kw in ['criminal', 'court', 'risk_score', 'empty'])
                        else 'HIGH',
                })

    all_failures.sort(key=lambda x: (x['priority'] == 'HIGH', x['candidate_id']))

    # Generate markdown
    md = f"""# E2E TEST REPORT
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

## EXECUTIVE SUMMARY

| Metric | Value |
|--------|-------|
| Candidates Tested | {len(validations)} |
| PASS | {val_totals.get('pass', 0)} |
| FAIL | {val_totals.get('fail', 0)} |
| WARN | {val_totals.get('warn', 0)} |
| Pipeline Bugs | {total_bugs} |
| Silent Failures | {total_silent} |

## RESULTS BY CANDIDATE

"""
    for v in validations:
        icon = {'PASS': 'PASS', 'FAIL': 'FAIL', 'WARN': 'WARN'}.get(v['verdict'], '?')
        md += f"### {icon} [{v['candidate_id']:02d}] {v['full_name']}\n"
        md += f"- **Risk Level**: {v.get('expected_risk', '?')}\n"
        md += f"- **Verdict**: {v['verdict']} ({v['pass_rate']}% pass rate)\n"

        fails = [(f, val[1]) for f, val in (v.get('validations') or {}).items()
                 if val[0] == 'FAIL']
        warns = [(f, val[1]) for f, val in (v.get('validations') or {}).items()
                 if val[0] == 'WARN']

        if fails:
            md += "- **Failures**:\n"
            for f, d in fails:
                md += f"  - `{f}`: {d}\n"
        if warns:
            md += "- **Warnings**:\n"
            for f, d in warns[:3]:
                md += f"  - `{f}`: {d}\n"
        md += "\n"

    if all_failures:
        md += "## PRIORITY FIXES REQUIRED\n\n"
        for i, fail in enumerate(all_failures, 1):
            md += f"{i}. **[{fail['priority']}]** `{fail['field']}` for {fail['candidate']}\n"
            md += f"   {fail['detail']}\n\n"

    md += """## HOW TO RE-RUN

```bash
cd C:\\Users\\fedor\\ibp
python scripts/e2e/phase0_capability_discovery.py
python scripts/e2e/candidate_runner.py
python scripts/e2e/spectator.py
python scripts/e2e/output_validator.py
python scripts/e2e/final_report.py
```
"""

    with open(FINAL_REPORT_MD, 'w', encoding='utf-8') as f:
        f.write(md)

    final = {
        'timestamp': datetime.utcnow().isoformat(),
        'summary': {
            'candidates': len(validations),
            'pass': val_totals.get('pass', 0),
            'fail': val_totals.get('fail', 0),
            'warn': val_totals.get('warn', 0),
            'pipeline_bugs': total_bugs,
            'silent_failures': total_silent,
        },
        'all_failures': all_failures,
    }
    with open(FINAL_REPORT, 'w', encoding='utf-8') as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(md)
    print(f"Reports saved:")
    print(f"   {FINAL_REPORT}")
    print(f"   {FINAL_REPORT_MD}")


if __name__ == '__main__':
    generate_final_report()
