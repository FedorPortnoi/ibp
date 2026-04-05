"""
AGENT 9: FINAL AGGREGATOR + HEALTH SCORE CALCULATOR
=====================================================
Combines all agent results.
Calculates overall health score.
Generates final markdown report.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

PROJECT_ROOT = Path(r"C:\Users\fedor\ibp")
AUDIT_DIR = PROJECT_ROOT / 'scripts' / 'audit'
REPORT_FILE = PROJECT_ROOT / 'scripts' / 'audit' / 'INFRASTRUCTURE_REPORT.md'

SEVERITY_WEIGHTS = {
    'CRITICAL': 25,
    'HIGH': 10,
    'MEDIUM': 3,
    'LOW': 1,
}

def load_all_results():
    all_findings = []
    for i in range(1, 9):
        result_file = AUDIT_DIR / f'agent{i}_results.json'
        if result_file.exists():
            with open(result_file, encoding='utf-8') as f:
                findings = json.load(f)
                all_findings.extend(findings)
                print(f"  Loaded agent{i}: {len(findings)} findings")
        else:
            print(f"  WARNING: agent{i}_results.json not found")
    return all_findings

def calculate_health_score(findings):
    """
    Health score: 100 = perfect, 0 = critical.
    Capped deductions per severity to avoid one bucket dominating.
    """
    from collections import Counter
    severity_counts = Counter(f['severity'] for f in findings)

    # Per-finding deduction and max cap per severity
    DEDUCTION_CONFIG = {
        'CRITICAL': (25, 50),   # 25 per finding, max 50
        'HIGH':     (2, 30),    # 2 per finding, max 30
        'MEDIUM':   (0.5, 10),  # 0.5 per finding, max 10
        'LOW':      (0.1, 5),   # 0.1 per finding, max 5
    }

    deductions = 0
    for severity, (per_finding, cap) in DEDUCTION_CONFIG.items():
        count = severity_counts.get(severity, 0)
        deductions += min(count * per_finding, cap)

    score = max(0, round(100 - deductions))
    return score

def group_by_severity(findings):
    groups = defaultdict(list)
    for f in findings:
        groups[f['severity']].append(f)
    return groups

def generate_report(findings):
    groups = group_by_severity(findings)
    health_score = calculate_health_score(findings)

    if health_score >= 90:
        health_label = "EXCELLENT"
        health_desc = "System is running reliably"
    elif health_score >= 75:
        health_label = "GOOD"
        health_desc = "Minor issues found"
    elif health_score >= 60:
        health_label = "FAIR"
        health_desc = "Needs attention"
    elif health_score >= 40:
        health_label = "POOR"
        health_desc = "Significant issues"
    else:
        health_label = "CRITICAL"
        health_desc = "Requires immediate intervention"

    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    md = f"""# INFRASTRUCTURE AUDIT REPORT
**Generated:** {now}
**Project:** IBP (shtirletzsled.ru)

---

## HEALTH SCORE: {health_score}/100 -- {health_label}
> {health_desc}

| Severity | Count | Points Deducted (capped) |
|----------|-------|--------------------------|
| CRITICAL | {len(groups['CRITICAL'])} | {min(len(groups['CRITICAL']) * 25, 50)} |
| HIGH | {len(groups['HIGH'])} | {min(len(groups['HIGH']) * 2, 30)} |
| MEDIUM | {len(groups['MEDIUM'])} | {min(round(len(groups['MEDIUM']) * 0.5), 10)} |
| LOW | {len(groups['LOW'])} | {min(round(len(groups['LOW']) * 0.1), 5)} |
| **TOTAL** | **{len(findings)}** | **{100 - health_score}** |

---

## CRITICAL ISSUES ({len(groups['CRITICAL'])})
*These MUST be fixed immediately -- they cause crashes or data loss*

"""

    for f in groups['CRITICAL']:
        agent = f.get('agent', 'UNKNOWN')
        file = f.get('file', f.get('service', '?'))
        line = f.get('line', 0)
        md += f"### [{agent}] {file}"
        if line:
            md += f" (line {line})"
        md += f"\n**Issue:** {f['issue']}\n\n"
        md += f"**Fix:** {f['recommendation']}\n\n---\n\n"

    md += f"""## HIGH PRIORITY ({len(groups['HIGH'])})
*Fix these soon -- they cause freezes, errors, or data quality issues*

"""

    for f in groups['HIGH']:
        agent = f.get('agent', 'UNKNOWN')
        file = f.get('file', f.get('service', '?'))
        line = f.get('line', 0)
        md += f"### [{agent}] {file}"
        if line:
            md += f":{line}"
        md += f"\n- **Issue:** {f['issue']}\n"
        md += f"- **Fix:** {f['recommendation']}\n\n"

    md += f"""## MEDIUM PRIORITY ({len(groups['MEDIUM'])})
*Address in next development cycle*

"""

    for f in groups['MEDIUM']:
        file = f.get('file', f.get('service', '?'))
        line = f.get('line', 0)
        loc = f"{file}:{line}" if line else file
        md += f"- **{loc}** -- {f['issue']}\n"
        md += f"  *Fix: {f['recommendation']}*\n\n"

    md += f"""## LOW PRIORITY ({len(groups['LOW'])})
*Nice to have improvements*

"""

    for f in groups['LOW']:
        file = f.get('file', f.get('service', '?'))
        md += f"- {file}: {f['issue']}\n"

    # By agent summary
    md += "\n---\n\n## FINDINGS BY AGENT\n\n"

    agent_counts = defaultdict(lambda: defaultdict(int))
    for f in findings:
        agent = f.get('agent', 'UNKNOWN')
        agent_counts[agent][f['severity']] += 1

    md += "| Agent | Critical | High | Medium | Low | Total |\n"
    md += "|-------|----------|------|--------|-----|-------|\n"
    for agent, counts in sorted(agent_counts.items()):
        total = sum(counts.values())
        md += (f"| {agent} | {counts['CRITICAL']} | {counts['HIGH']} | "
               f"{counts['MEDIUM']} | {counts['LOW']} | {total} |\n")

    md += f"""
---

## ACTION PLAN

### Immediate (fix today):
"""
    for i, f in enumerate(groups['CRITICAL'][:5], 1):
        file = f.get('file', f.get('service', '?'))
        md += f"{i}. **{file}**: {f['recommendation']}\n"

    md += "\n### This week:\n"
    for i, f in enumerate(groups['HIGH'][:10], 1):
        file = f.get('file', f.get('service', '?'))
        md += f"{i}. {file}: {f['recommendation']}\n"

    md += f"""
---

## HOW TO RE-RUN THIS AUDIT
```bash
cd C:\\Users\\fedor\\ibp
python scripts/audit/run_full_audit.py
```

Report will be regenerated at: `scripts/audit/INFRASTRUCTURE_REPORT.md`
"""

    return md, health_score

# -- Main --
if __name__ == '__main__':
    print("=" * 70)
    print("AGENT 9: FINAL AGGREGATOR")
    print("=" * 70)

    findings = load_all_results()
    print(f"\nTotal findings: {len(findings)}")

    report_md, score = generate_report(findings)

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(report_md)

    print(f"\n{'='*70}")
    print(f"HEALTH SCORE: {score}/100")
    print(f"Report saved: {REPORT_FILE}")
    print(f"{'='*70}")

    with open(AUDIT_DIR / 'all_findings.json', 'w', encoding='utf-8') as f:
        json.dump(findings, f, ensure_ascii=False, indent=2)
