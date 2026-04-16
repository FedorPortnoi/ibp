# Runtime Gap Audit

Read-only local auditor for Stirlitz / IBP prerequisites and unresolved runtime truth gaps.

## Purpose

- inventory local prerequisite gaps without mutating repo state
- distinguish local configuration presence from true runtime readiness
- flag integrations that still need dashboard access, production-host access, or safe manual verification
- write machine-readable JSON plus a human-readable Markdown report

## Safety Guarantees

- no external requests
- no app-factory execution
- no database writes
- no login or code-send flows
- no secret values printed into reports
- no browser automation or dashboard scraping

## Usage

```bash
python tools/runtime_gap_audit.py
```

Optional flags:

```bash
python tools/runtime_gap_audit.py ^
  --repo-root . ^
  --brain-root "C:\Users\fedor\Documents\Fedor's Brain" ^
  --env-file .env ^
  --output-dir artifacts ^
  --report-prefix runtime_gap_audit
```

## Output Files

By default the tool writes:

- `artifacts/runtime_gap_audit.json`
- `artifacts/runtime_gap_audit.md`

## Output Schema

Each finding includes:

- `missing_item`
- `category`
- `current_status`
- `where_to_get_it`
- `how_to_verify_it`
- `confidence`
- `notes`

The JSON report also includes top-level `metadata` and `summary`.

## Status Vocabulary

Environment-variable findings use:

- `local-present`
- `local-missing`
- `optional`
- `unknown`

Other categories use explicit states such as:

- `present`
- `missing`
- `readable`
- `unreadable`
- `import-ok`
- `import-failed`
- `present-in-code`
- `missing-in-code`
- `unsafe-to-auto-run-read-only`
- `code-present; configured-locally; needs-safe-manual-verification`

## Notes

- `create_app()` is not executed by this tool because the current app factory performs writes (`db.create_all`, migration helpers, directory creation).
- Route coverage is collected statically from `app/routes/*.py` decorators.
- Sensitive values are never emitted. Presence is reported without printing the secret.
