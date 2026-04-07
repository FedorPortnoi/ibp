# E2E TEST REPORT
Generated: 2026-04-02 14:58 UTC

## EXECUTIVE SUMMARY

| Metric | Value |
|--------|-------|
| Candidates Tested | 10 |
| PASS | 5 |
| FAIL | 5 |
| WARN | 0 |
| Pipeline Bugs | 0 |
| Silent Failures | 6 |

## RESULTS BY CANDIDATE

### FAIL [01] Зобов Андрей Борисович
- **Risk Level**: HIGH
- **Verdict**: FAIL (84.6% pass rate)
- **Failures**:
  - `risk_score`: Score 0/100 too low for HIGH (expected >=40)
  - `risk_score_zero`: Risk score is 0 for a HIGH candidate -- scoring did not run
- **Warnings**:
  - `optional_fields`: Missing: geo_intelligence, geo_analysis, text_analysis, activity_timeline

### FAIL [02] Котов Валерий Дмитриевич
- **Risk Level**: HIGH
- **Verdict**: FAIL (83.3% pass rate)
- **Failures**:
  - `risk_score`: Score 0/100 too low for HIGH (expected >=40)
  - `risk_score_zero`: Risk score is 0 for a HIGH candidate -- scoring did not run
- **Warnings**:
  - `optional_fields`: Missing: business_records, geo_intelligence, geo_analysis, text_analysis, activity_timeline

### FAIL [03] Шаламов Евгений Анатольевич
- **Risk Level**: CRITICAL
- **Verdict**: FAIL (80.0% pass rate)
- **Failures**:
  - `fssp`: MISSING: Known FSSP debts not found
  - `risk_score`: Score 0/100 too low for CRITICAL (expected >=60)
  - `risk_score_zero`: Risk score is 0 for a CRITICAL candidate -- scoring did not run
- **Warnings**:
  - `optional_fields`: Missing: geo_intelligence, geo_analysis, text_analysis, activity_timeline

### PASS [04] Четвериков Валерий Викторович
- **Risk Level**: LOW
- **Verdict**: PASS (100.0% pass rate)
- **Warnings**:
  - `optional_fields`: Missing: geo_intelligence, geo_analysis, text_analysis, activity_timeline

### PASS [05] Гнездилова Арина Сергеевна
- **Risk Level**: LOW
- **Verdict**: PASS (100.0% pass rate)
- **Warnings**:
  - `optional_fields`: Missing: business_records, geo_intelligence, geo_analysis, text_analysis, activity_timeline

### PASS [06] Григоренко Вадим Павлович
- **Risk Level**: LOW
- **Verdict**: PASS (100.0% pass rate)
- **Warnings**:
  - `optional_fields`: Missing: business_records, geo_intelligence, geo_analysis, text_analysis, activity_timeline

### FAIL [07] Фомичев Вячеслав Владиславович
- **Risk Level**: LOW
- **Verdict**: FAIL (0.0% pass rate)

### FAIL [08] Волков Сергей Алексеевич
- **Risk Level**: CRITICAL
- **Verdict**: FAIL (69.2% pass rate)
- **Failures**:
  - `fssp`: MISSING: Known FSSP debts not found
  - `risk_score`: Score 0/100 too low for CRITICAL (expected >=60)
  - `risk_score_zero`: Risk score is 0 for a CRITICAL candidate -- scoring did not run
  - `flag_1`: NO EVIDENCE: 'Участник СВО — ЧВК Вагнер (2022-2023)' not in dossier
- **Warnings**:
  - `optional_fields`: Missing: business_records, geo_intelligence, geo_analysis, text_analysis, activity_timeline

### PASS [09] Калмыков Александр Николаевич
- **Risk Level**: LOW
- **Verdict**: PASS (100.0% pass rate)

### PASS [10] Плисенко Любовь Григорьевна
- **Risk Level**: LOW
- **Verdict**: PASS (100.0% pass rate)
- **Warnings**:
  - `optional_fields`: Missing: business_records, geo_intelligence, geo_analysis, text_analysis, activity_timeline

## PRIORITY FIXES REQUIRED

1. **[HIGH]** `risk_score` for Зобов Андрей Борисович
   Score 0/100 too low for HIGH (expected >=40)

2. **[HIGH]** `risk_score_zero` for Зобов Андрей Борисович
   Risk score is 0 for a HIGH candidate -- scoring did not run

3. **[HIGH]** `risk_score` for Котов Валерий Дмитриевич
   Score 0/100 too low for HIGH (expected >=40)

4. **[HIGH]** `risk_score_zero` for Котов Валерий Дмитриевич
   Risk score is 0 for a HIGH candidate -- scoring did not run

5. **[HIGH]** `fssp` for Шаламов Евгений Анатольевич
   MISSING: Known FSSP debts not found

6. **[HIGH]** `risk_score` for Шаламов Евгений Анатольевич
   Score 0/100 too low for CRITICAL (expected >=60)

7. **[HIGH]** `risk_score_zero` for Шаламов Евгений Анатольевич
   Risk score is 0 for a CRITICAL candidate -- scoring did not run

8. **[HIGH]** `fssp` for Волков Сергей Алексеевич
   MISSING: Known FSSP debts not found

9. **[HIGH]** `risk_score` for Волков Сергей Алексеевич
   Score 0/100 too low for CRITICAL (expected >=60)

10. **[HIGH]** `risk_score_zero` for Волков Сергей Алексеевич
   Risk score is 0 for a CRITICAL candidate -- scoring did not run

11. **[HIGH]** `flag_1` for Волков Сергей Алексеевич
   NO EVIDENCE: 'Участник СВО — ЧВК Вагнер (2022-2023)' not in dossier

## HOW TO RE-RUN

```bash
cd C:\Users\fedor\ibp
python scripts/e2e/phase0_capability_discovery.py
python scripts/e2e/candidate_runner.py
python scripts/e2e/spectator.py
python scripts/e2e/output_validator.py
python scripts/e2e/final_report.py
```
