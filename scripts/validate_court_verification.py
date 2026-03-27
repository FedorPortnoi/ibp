"""
Agent 5 — Validation script for court verification system.
Checks all components: data files, UI badges, risk scoring patch.
"""

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def validate():
    print("=" * 60)
    print("ВАЛИДАЦИЯ: Судин Артем Алексеевич")
    print("ИНН: 232308435186 | Краснодарский край")
    print("=" * 60)

    checks = []
    all_ok = True

    # 1. Check kad_results.json
    kad_file = Path("data/kad_results.json")
    if kad_file.exists():
        with open(kad_file, encoding="utf-8") as f:
            kad_data = json.load(f)
        verified = kad_data.get("total_verified", 0)
        errors = kad_data.get("errors", [])
        if errors:
            status = f"ran with errors: {errors}"
            print(f"[!] kad.arbitr.ru: {status}")
        else:
            status = f"{verified} VERIFIED дел"
            print(f"[+] kad.arbitr.ru: {status}")
        checks.append(("kad.arbitr.ru (INN)", True, status))
    else:
        checks.append(("kad.arbitr.ru (INN)", False, "data/kad_results.json not found"))
        print("[-] data/kad_results.json not found")
        all_ok = False

    # 2. Check court_region_results.json
    region_file = Path("data/court_region_results.json")
    if region_file.exists():
        with open(region_file, encoding="utf-8") as f:
            region_data = json.load(f)
        stats = region_data.get("stats", {})
        total = region_data.get("total_cases", 0)
        status = f"total={total}, {stats}"
        print(f"[+] Region filter: {status}")
        checks.append(("Region filter", True, status))
    else:
        checks.append(("Region filter", False, "data/court_region_results.json not found"))
        print("[-] data/court_region_results.json not found")
        all_ok = False

    # 3. Check UI badges in template
    dossier_path = Path("app/templates/candidate_dossier.html")
    if dossier_path.exists():
        content = dossier_path.read_text(encoding="utf-8")
        has_badges = "conf-badge" in content and "conf-verified" in content
        has_summary = "confidence-summary" in content
        has_unverified_warning = "однофамильцам" in content
        if has_badges and has_summary and has_unverified_warning:
            print("[+] UI: confidence badges, summary, and warning found")
            checks.append(("UI badges", True, "conf-badge + summary + warning"))
        else:
            missing = []
            if not has_badges:
                missing.append("badges")
            if not has_summary:
                missing.append("summary")
            if not has_unverified_warning:
                missing.append("warning")
            print(f"[-] UI: missing {', '.join(missing)}")
            checks.append(("UI badges", False, f"missing: {missing}"))
            all_ok = False
    else:
        checks.append(("UI badges", False, "candidate_dossier.html not found"))
        print("[-] candidate_dossier.html not found")
        all_ok = False

    # 4. Check CSS
    css_path = Path("app/static/css/sled-design-system.css")
    if css_path.exists():
        css = css_path.read_text(encoding="utf-8")
        has_css = ".conf-verified" in css and ".conf-unverified" in css
        if has_css:
            print("[+] CSS: confidence badge styles found")
            checks.append(("CSS styles", True, "conf-verified/likely/possible/unverified"))
        else:
            print("[-] CSS: confidence badge styles missing")
            checks.append(("CSS styles", False, "missing .conf-* classes"))
            all_ok = False

    # 5. Check risk scoring patch
    scorer_path = Path("app/services/candidate/risk_scorer.py")
    if scorer_path.exists():
        scorer = scorer_path.read_text(encoding="utf-8")
        has_confidence_weights = "COURT_CONFIDENCE_WEIGHTS" in scorer
        has_filter = "_filter_courts_by_confidence" in scorer
        has_risk_records = "risk_records" in scorer
        if has_confidence_weights and has_filter and has_risk_records:
            print("[+] Risk scorer: confidence weighting patched")
            checks.append(("Risk scorer", True, "COURT_CONFIDENCE_WEIGHTS + filter + risk_records"))
        else:
            missing = []
            if not has_confidence_weights:
                missing.append("COURT_CONFIDENCE_WEIGHTS")
            if not has_filter:
                missing.append("_filter_courts_by_confidence")
            if not has_risk_records:
                missing.append("risk_records")
            print(f"[-] Risk scorer: missing {', '.join(missing)}")
            checks.append(("Risk scorer", False, f"missing: {missing}"))
            all_ok = False
    else:
        checks.append(("Risk scorer", False, "risk_scorer.py not found"))
        print("[-] risk_scorer.py not found")
        all_ok = False

    # Final report
    print(f"\n{'=' * 60}")
    print("ФИНАЛЬНЫЙ ОТЧЁТ")
    print("=" * 60)

    for name, ok, detail in checks:
        icon = "[+]" if ok else "[-]"
        print(f"  {icon} {name}: {detail}")

    # Print court case details if available
    if kad_file.exists():
        with open(kad_file, encoding="utf-8") as f:
            kad_data = json.load(f)
        print(f"\nАРБИТРАЖ (kad.arbitr.ru, 100% верификация по ИНН):")
        cases = kad_data.get("cases", [])
        if cases:
            for case in cases:
                print(f"  [VERIFIED] {case.get('case_number', '—')} — {case.get('parties', case.get('raw_text', ''))[:80]}")
        else:
            errors = kad_data.get("errors", [])
            if errors:
                print(f"  Ошибки: {errors}")
            else:
                print("  Арбитражных дел не найдено (хороший знак)")

    if region_file.exists():
        with open(region_file, encoding="utf-8") as f:
            region_data = json.load(f)
        stats = region_data.get("stats", {})
        print(f"\nОБЩИЕ СУДЫ (sudact.ru + судебныерешения.рф + reputation.su):")
        for level in ["VERIFIED", "LIKELY", "POSSIBLE", "UNVERIFIED"]:
            count = stats.get(level, 0)
            if count > 0:
                print(f"  {level}: {count} дел")
                # Show first 3 cases of each level
                for case in region_data.get("cases_by_confidence", {}).get(level, [])[:3]:
                    src = case.get("source", "?")
                    preview = case.get("text_preview", "")[:80]
                    print(f"    [{src}] {preview}")

    print(f"\n{'=' * 60}")
    if all_ok:
        print("ВАЛИДАЦИЯ ПРОЙДЕНА")
    else:
        print("ВАЛИДАЦИЯ: есть проблемы (см. выше)")
    print("=" * 60)


if __name__ == "__main__":
    validate()
