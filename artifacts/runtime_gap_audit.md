# Runtime Gap Audit

## Metadata
- generated_at: `2026-04-15T22:46:05.444998+00:00`
- repo_root: `C:\Users\fedor\ibp`
- brain_root: `C:\Users\fedor\Documents\Fedor's Brain`
- env_file: `C:\Users\fedor\ibp\.env`
- report_prefix: `runtime_gap_audit`

## Summary
- total_findings: `105`
- missing_like_findings: `26`
- categories: `{"database": 2, "environment_variable": 32, "file_prerequisite": 9, "integration_readiness": 22, "runtime_readiness": 9, "runtime_route": 12, "source_of_truth_file": 7, "tool_prerequisite": 6, "vault_reference": 6}`

## database

| missing_item | current_status | where_to_get_it | how_to_verify_it | confidence | notes |
| --- | --- | --- | --- | --- | --- |
| local_leak_db_readability | readable | already local | Open the SQLite file read-only and run PRAGMA quick_check plus a table inventory. | high | quick_check=ok; tables=2; sample=leak_records, sqlite_sequence |
| primary_db_readability | readable | already local | Open the SQLite file read-only and run PRAGMA quick_check plus a table inventory. | high | quick_check=ok; tables=9; sample=business_records, candidate_checks, connections, court_records, friends, investigations, social_profiles, subscriptions |

## environment_variable

| missing_item | current_status | where_to_get_it | how_to_verify_it | confidence | notes |
| --- | --- | --- | --- | --- | --- |
| ANTHROPIC_API_KEY | local-present | Anthropic dashboard or secret store | Check effective local runtime environment and .env for ANTHROPIC_API_KEY. | high | Claude integration key. Presence only; value masked. Sources=process-env, dotenv-file. |
| DATABASE_URL | optional | local .env or host environment | Check effective local runtime environment and .env for DATABASE_URL. | high | optional; SQLite fallback exists. Presence only; value masked. Sources=none. |
| DEHASHED_API_KEY | optional | DeHashed dashboard or secret store | Check effective local runtime environment and .env for DEHASHED_API_KEY. | high | DeHashed credential. Presence only; value masked. Sources=none. |
| DEHASHED_API_SECRET | optional | DeHashed dashboard or secret store | Check effective local runtime environment and .env for DEHASHED_API_SECRET. | high | DeHashed credential. Presence only; value masked. Sources=none. |
| DEHASHED_USERNAME | optional | DeHashed dashboard or secret store | Check effective local runtime environment and .env for DEHASHED_USERNAME. | high | DeHashed credential. Presence only; value masked. Sources=none. |
| ENABLE_GEO_RESTRICTED_CHECKERS | optional | local .env or host environment | Check effective local runtime environment and .env for ENABLE_GEO_RESTRICTED_CHECKERS. | high | geo-restricted sources flag. Presence only; value masked. Sources=none. |
| ENABLE_PEOPLE_SEARCH | local-present | local .env or host environment | Check effective local runtime environment and .env for ENABLE_PEOPLE_SEARCH. | high | feature flag. Presence only; value masked. Sources=process-env, dotenv-file. |
| FLASK_ENV | local-present | local .env or host environment | Check effective local runtime environment and .env for FLASK_ENV. | high | selects config profile. Presence only; value masked. Sources=process-env, dotenv-file. |
| FSSP_API_TOKEN | optional | FSSP provider account or secret store | Check effective local runtime environment and .env for FSSP_API_TOKEN. | high | official FSSP token. Presence only; value masked. Sources=none. |
| GETCONTACT_API_KEY | optional | GetContact dashboard or secret store | Check effective local runtime environment and .env for GETCONTACT_API_KEY. | high | GetContact API mode. Presence only; value masked. Sources=none. |
| GETCONTACT_API_URL | optional | GetContact partner docs or secret store | Check effective local runtime environment and .env for GETCONTACT_API_URL. | high | GetContact API mode. Presence only; value masked. Sources=none. |
| GETCONTACT_HMAC_SECRET | optional | GetContact dashboard or secret store | Check effective local runtime environment and .env for GETCONTACT_HMAC_SECRET. | high | GetContact API mode. Presence only; value masked. Sources=none. |
| GETCONTACT_PARTNER_ID | optional | GetContact dashboard or secret store | Check effective local runtime environment and .env for GETCONTACT_PARTNER_ID. | high | GetContact API mode. Presence only; value masked. Sources=none. |
| HIBP_API_KEY | optional | HIBP dashboard or secret store | Check effective local runtime environment and .env for HIBP_API_KEY. | high | HIBP paid mode. Presence only; value masked. Sources=none. |
| HUNTER_API_KEY | optional | Hunter dashboard or secret store | Check effective local runtime environment and .env for HUNTER_API_KEY. | high | Hunter API key. Presence only; value masked. Sources=none. |
| IBP_SESSION_REMEMBER | optional | local .env or host environment | Check effective local runtime environment and .env for IBP_SESSION_REMEMBER. | high | optional remember-me override. Presence only; value masked. Sources=none. |
| IBP_SESSION_TIMEOUT | optional | local .env or host environment | Check effective local runtime environment and .env for IBP_SESSION_TIMEOUT. | high | optional timeout override. Presence only; value masked. Sources=none. |
| LEAKCHECK_API_KEY | optional | LeakCheck dashboard or secret store | Check effective local runtime environment and .env for LEAKCHECK_API_KEY. | high | paid LeakCheck. Presence only; value masked. Sources=none. |
| MAILCAT_API_KEY | optional | provider docs or secret store | Check effective local runtime environment and .env for MAILCAT_API_KEY. | high | Mailcat integration if adopted. Presence only; value masked. Sources=none. |
| RESEND_API_KEY | optional | Resend dashboard or secret store | Check effective local runtime environment and .env for RESEND_API_KEY. | high | email delivery key. Presence only; value masked. Sources=none. |
| SEARCH4FACES_API_KEY | optional | provider dashboard or secret store | Check effective local runtime environment and .env for SEARCH4FACES_API_KEY. | high | face-search API key. Presence only; value masked. Sources=none. |
| SECRET_KEY | local-present | local .env or host secret manager | Check effective local runtime environment and .env for SECRET_KEY. | high | required for app startup. Presence only; value masked. Sources=process-env, dotenv-file. |
| SNUSBASE_API_KEY | optional | Snusbase dashboard or secret store | Check effective local runtime environment and .env for SNUSBASE_API_KEY. | high | Snusbase credential. Presence only; value masked. Sources=none. |
| TELEGRAM_API_HASH | local-present | my.telegram.org or secret store | Check effective local runtime environment and .env for TELEGRAM_API_HASH. | high | Telethon credential. Presence only; value masked. Sources=process-env, dotenv-file. |
| TELEGRAM_API_ID | local-present | my.telegram.org or secret store | Check effective local runtime environment and .env for TELEGRAM_API_ID. | high | Telethon credential. Presence only; value masked. Sources=process-env, dotenv-file. |
| TELEGRAM_PHONE | local-present | local .env only | Check effective local runtime environment and .env for TELEGRAM_PHONE. | high | Telethon phone. Presence only; value masked. Sources=process-env, dotenv-file. |
| VK_LOGIN | local-present | local .env only | Check effective local runtime environment and .env for VK_LOGIN. | high | VK browser-login prerequisite. Presence only; value masked. Sources=process-env, dotenv-file. |
| VK_LOGIN_EMAIL | local-present | local .env only | Check effective local runtime environment and .env for VK_LOGIN_EMAIL. | high | VK browser-login prerequisite. Presence only; value masked. Sources=process-env, dotenv-file. |
| VK_PASSWORD | local-present | local .env only | Check effective local runtime environment and .env for VK_PASSWORD. | high | VK browser-login prerequisite. Presence only; value masked. Sources=process-env, dotenv-file. |
| VK_SERVICE_TOKEN | optional | VK dashboard or secret store | Check effective local runtime environment and .env for VK_SERVICE_TOKEN. | high | VK service token. Presence only; value masked. Sources=none. |
| VK_TOKEN | local-present | legacy .env or secret store | Check effective local runtime environment and .env for VK_TOKEN. | high | legacy VK token alias. Presence only; value masked. Sources=process-env, dotenv-file. |
| VK_USER_TOKEN | local-present | VK OAuth or secret store | Check effective local runtime environment and .env for VK_USER_TOKEN. | high | VK user token. Presence only; value masked. Sources=process-env, dotenv-file. |

## file_prerequisite

| missing_item | current_status | where_to_get_it | how_to_verify_it | confidence | notes |
| --- | --- | --- | --- | --- | --- |
| demo_getcontact_data | present | already in repo demo data | check whether the demo GetContact dataset exists | high | demo fallback asset; path=C:\Users\fedor\ibp\data\demo\getcontact_demo.jsonl size=12724 |
| demo_telco_data | present | already in repo demo data | check whether the demo telco dataset exists | high | demo fallback asset; path=C:\Users\fedor\ibp\data\demo\telco_demo.csv size=14143 |
| demo_vk2012_data | present | already in repo demo data | check whether the demo VK 2012 dataset exists | high | demo fallback asset; path=C:\Users\fedor\ibp\data\demo\vk_2012_demo.csv size=10967 |
| dotenv_file | present | local repo root | check whether the repo-local .env file exists | high | values stay masked; path=C:\Users\fedor\ibp\.env size=1881 |
| local_leak_db | present | local data snapshot / internal dataset location | check whether the local leak DB exists | high | absence blocks leak-db-backed sources; path=C:\Users\fedor\ibp\data\leaks\all_leaks.db size=32768 |
| primary_db | present | local runtime data directory or deployment snapshot | check whether the primary SQLite DB exists | high | read-only SQLite probe runs separately; path=C:\Users\fedor\ibp\ibp_investigations.db size=102400 |
| telethon_session | missing | run scripts/auth_telegram.py interactively on the owner machine | check whether the Telethon session exists | high | required for Telegram Method C; path=C:\Users\fedor\ibp\tg_session\ibp_session.session |
| vk_state_cache | present | populate via the local VK login flow | check whether the VK state cache exists | high | presence does not prove freshness; path=C:\Users\fedor\ibp\vk_session\state.json size=180 |
| vk_web_token_cache | present | populate via the local VK login flow | check whether the VK web-token cache exists | high | presence does not prove freshness; path=C:\Users\fedor\ibp\vk_session\web_token.json size=285 |

## integration_readiness

| missing_item | current_status | where_to_get_it | how_to_verify_it | confidence | notes |
| --- | --- | --- | --- | --- | --- |
| Claude / Anthropic | code-present; configured-locally; needs-dashboard-access; needs-safe-manual-verification | Anthropic dashboard or secret store | Confirm local key presence, then verify only if the code path is re-enabled. | high | Key presence does not override the current hard-disabled code path. env_present=['ANTHROPIC_API_KEY'] env_missing=['none'] files_present=['none'] files_missing=['none'] commands_present=['none'] commands_missing=['none'] |
| DeHashed | code-present; blocked-by-missing-secret; needs-dashboard-access; needs-safe-manual-verification | DeHashed dashboard or secret store | Confirm credentials locally, then verify with a single approved lookup after the stubbed code is implemented. | high | Code path is currently stubbed/TODO. env_present=['none'] env_missing=['DEHASHED_USERNAME', 'DEHASHED_API_KEY', 'DEHASHED_API_SECRET'] files_present=['none'] files_missing=['none'] commands_present=['none'] commands_missing=['none'] |
| FSSP API / site path | code-present; blocked-by-missing-secret; needs-dashboard-access; needs-production-host-access; needs-safe-manual-verification | FSSP account, local env, and Russian-host runtime | Confirm local token/flag, then verify from the production or Russian host with a safe manual check. | high | env_present=['none'] env_missing=['FSSP_API_TOKEN', 'ENABLE_GEO_RESTRICTED_CHECKERS'] files_present=['none'] files_missing=['none'] commands_present=['none'] commands_missing=['none'] |
| Geo-restricted checkers | code-present; blocked-by-missing-secret; needs-production-host-access; needs-safe-manual-verification | production/Russian host access plus local env toggle | Verify only from the production-compatible host with explicitly approved manual checks. | high | env_present=['none'] env_missing=['ENABLE_GEO_RESTRICTED_CHECKERS'] files_present=['none'] files_missing=['none'] commands_present=['none'] commands_missing=['none'] |
| GetContact real API | code-present; blocked-by-missing-secret; needs-dashboard-access; needs-safe-manual-verification | GetContact partner dashboard or secret store | Confirm local keys, then run an approved low-volume manual probe. | high | env_present=['none'] env_missing=['GETCONTACT_API_URL', 'GETCONTACT_API_KEY', 'GETCONTACT_PARTNER_ID', 'GETCONTACT_HMAC_SECRET'] files_present=['none'] files_missing=['none'] commands_present=['none'] commands_missing=['none'] |
| HIBP paid API | code-present; blocked-by-missing-secret; needs-dashboard-access; needs-safe-manual-verification | HIBP dashboard or secret store | Confirm the key locally, then verify with a single approved lookup after the paid path is implemented. | high | env_present=['none'] env_missing=['HIBP_API_KEY'] files_present=['none'] files_missing=['none'] commands_present=['none'] commands_missing=['none'] |
| Holehe CLI | code-present; configured-locally; needs-safe-manual-verification | local Python environment / PATH | Confirm the CLI is on PATH or use the library path manually. | high | env_present=['none'] env_missing=['none'] files_present=['none'] files_missing=['none'] commands_present=['holehe'] commands_missing=['none'] |
| Hunter.io | code-present; blocked-by-missing-secret; needs-dashboard-access; needs-safe-manual-verification | Hunter dashboard or secret store | Confirm key presence locally, then use an approved low-volume manual probe. | high | env_present=['none'] env_missing=['HUNTER_API_KEY'] files_present=['none'] files_missing=['none'] commands_present=['none'] commands_missing=['none'] |
| LeakCheck paid mode | code-present; blocked-by-missing-secret; needs-dashboard-access; needs-safe-manual-verification | LeakCheck dashboard or secret store | Confirm the key locally, then run a single approved manual lookup. | high | env_present=['none'] env_missing=['LEAKCHECK_API_KEY'] files_present=['none'] files_missing=['none'] commands_present=['none'] commands_missing=['none'] |
| Local leak DB sources | code-present; configured-locally; needs-safe-manual-verification | internal/local data snapshot | Confirm the SQLite file exists and opens read-only, then verify schema and source coverage manually. | high | env_present=['none'] env_missing=['none'] files_present=['data/leaks/all_leaks.db'] files_missing=['none'] commands_present=['none'] commands_missing=['none'] |
| Maigret CLI | code-present; configured-locally; needs-safe-manual-verification | local Python environment / PATH | Confirm the CLI is on PATH and run a deliberately approved username check manually. | high | env_present=['none'] env_missing=['none'] files_present=['none'] files_missing=['none'] commands_present=['maigret'] commands_missing=['none'] |
| Mailcat | code-present; blocked-by-missing-secret-tooling; needs-safe-manual-verification | local tool install and any related provider config | Confirm the CLI is on PATH and any needed config exists locally before manual verification. | high | env_present=['none'] env_missing=['MAILCAT_API_KEY'] files_present=['none'] files_missing=['none'] commands_present=['none'] commands_missing=['mailcat'] |
| OpenSanctions | code-present; configured-locally; needs-safe-manual-verification | no local secret expected | Run a one-shot dummy-name check manually because external auth/reachability can drift. | high | Local config-free, but still depends on upstream behavior. env_present=['none'] env_missing=['none'] files_present=['none'] files_missing=['none'] commands_present=['none'] commands_missing=['none'] |
| Playwright / Chromium | code-present; configured-locally; needs-safe-manual-verification | local Python package plus Playwright browser install | Confirm the playwright module imports and browsers are installed before manual export verification. | high | This tool checks local package/browser-cache presence only; it does not launch a browser. env_present=['none'] env_missing=['none'] files_present=['none'] files_missing=['none'] commands_present=['none'] commands_missing=['none'] |
| Resend email | code-present; blocked-by-missing-secret; needs-dashboard-access; needs-safe-manual-verification | Resend dashboard or secret store | Confirm key presence locally, then use a non-billable or explicitly approved manual email test. | high | env_present=['none'] env_missing=['RESEND_API_KEY'] files_present=['none'] files_missing=['none'] commands_present=['none'] commands_missing=['none'] |
| Search4Faces API | code-present; blocked-by-missing-secret; needs-dashboard-access; needs-safe-manual-verification | provider dashboard or secret store | Confirm key presence locally, then run manual verification with approved test media. | high | env_present=['none'] env_missing=['SEARCH4FACES_API_KEY'] files_present=['none'] files_missing=['none'] commands_present=['none'] commands_missing=['none'] |
| Sherlock CLI | code-present; configured-locally; needs-safe-manual-verification | local Python environment / PATH | Confirm the CLI is on PATH and run a deliberately approved username check manually. | high | env_present=['none'] env_missing=['none'] files_present=['none'] files_missing=['none'] commands_present=['sherlock'] commands_missing=['none'] |
| Snoop CLI | code-present; blocked-by-missing-tooling; needs-safe-manual-verification | local tool install / PATH | Confirm the CLI is on PATH and any required dataset/setup exists before manual verification. | high | env_present=['none'] env_missing=['none'] files_present=['none'] files_missing=['none'] commands_present=['none'] commands_missing=['snoop'] |
| Snusbase | code-present; blocked-by-missing-secret; needs-dashboard-access; needs-safe-manual-verification | Snusbase dashboard or secret store | Confirm the key locally, then verify with an approved lookup after the stubbed code is implemented. | high | Code path is currently stubbed/TODO. env_present=['none'] env_missing=['SNUSBASE_API_KEY'] files_present=['none'] files_missing=['none'] commands_present=['none'] commands_missing=['none'] |
| Telethon session | code-present; blocked-by-missing-session-or-file; needs-safe-manual-verification | Run scripts/auth_telegram.py interactively on the owner machine | Confirm creds plus session file, then use a local status endpoint or one-shot health check manually. | high | env_present=['TELEGRAM_API_ID', 'TELEGRAM_API_HASH', 'TELEGRAM_PHONE'] env_missing=['none'] files_present=['none'] files_missing=['tg_session/ibp_session.session'] commands_present=['none'] commands_missing=['none'] |
| VK service token | code-present; blocked-by-missing-secret; needs-dashboard-access; needs-safe-manual-verification | VK dashboard or secret store | Confirm env presence and caches, then run one safe manual VK probe. | high | Missing service token usually leaves VK service flows in demo mode. env_present=['none'] env_missing=['VK_SERVICE_TOKEN'] files_present=['vk_session/state.json', 'vk_session/web_token.json'] files_missing=['none'] commands_present=['none'] commands_missing=['none'] |
| VK user token | code-present; configured-locally; needs-safe-manual-verification | VK OAuth flow or secret store | Confirm local token presence, then run one safe manual VK API probe. | high | Presence only; validity still needs a manual check. env_present=['VK_USER_TOKEN', 'VK_TOKEN'] env_missing=['none'] files_present=['none'] files_missing=['none'] commands_present=['none'] commands_missing=['none'] |

## runtime_readiness

| missing_item | current_status | where_to_get_it | how_to_verify_it | confidence | notes |
| --- | --- | --- | --- | --- | --- |
| app_import | import-ok | app.py / package in repo | Import app with bytecode writes disabled. | high | import-ok |
| config_import | import-ok | config.py / package in repo | Import config with bytecode writes disabled. | high | import-ok |
| create_app_factory | unsafe-to-auto-run-read-only | app/__init__.py | Review create_app statically; only execute it intentionally if write-side effects are acceptable. | high | Detected side effects: _migrate_task_columns, _migrate_user_columns, db.create_all, db.session.commit, os.makedirs |
| DEMO_MODE_PREDICTED | known | config.py and effective local env | Inspect config.py and local env handling for DEMO_MODE_PREDICTED. | high | Derived value=True |
| ENABLE_GEO_RESTRICTED_CHECKERS | unknown | config.py and effective local env | Inspect config.py and local env handling for ENABLE_GEO_RESTRICTED_CHECKERS. | medium | Derived value=None |
| ENABLE_PEOPLE_SEARCH | known | config.py and effective local env | Inspect config.py and local env handling for ENABLE_PEOPLE_SEARCH. | high | Derived value=True |
| SESSION_COOKIE_HTTPONLY | known | config.py and effective local env | Inspect config.py and local env handling for SESSION_COOKIE_HTTPONLY. | high | Derived value=True |
| SESSION_COOKIE_SAMESITE | known | config.py and effective local env | Inspect config.py and local env handling for SESSION_COOKIE_SAMESITE. | high | Derived value='Lax' |
| SESSION_COOKIE_SECURE | known | config.py and effective local env | Inspect config.py and local env handling for SESSION_COOKIE_SECURE. | high | Derived value=True |

## runtime_route

| missing_item | current_status | where_to_get_it | how_to_verify_it | confidence | notes |
| --- | --- | --- | --- | --- | --- |
| /candidate/history | missing-in-code | app/routes/*.py | Parse route decorators statically to avoid calling the app factory in read-only mode. | high | methods=['none'] |
| /candidate/new | missing-in-code | app/routes/*.py | Parse route decorators statically to avoid calling the app factory in read-only mode. | high | methods=['none'] |
| /candidate/progress/<task_id>/status | missing-in-code | app/routes/*.py | Parse route decorators statically to avoid calling the app factory in read-only mode. | high | methods=['none'] |
| /candidate/start | missing-in-code | app/routes/*.py | Parse route decorators statically to avoid calling the app factory in read-only mode. | high | methods=['none'] |
| /health | present-in-code | app/routes/*.py | Parse route decorators statically to avoid calling the app factory in read-only mode. | high | methods=['GET'] |
| /login | present-in-code | app/routes/*.py | Parse route decorators statically to avoid calling the app factory in read-only mode. | high | methods=['GET,POST'] |
| /phase2/api/sources/status | missing-in-code | app/routes/*.py | Parse route decorators statically to avoid calling the app factory in read-only mode. | high | methods=['none'] |
| /phase2/api/telegram/status | missing-in-code | app/routes/*.py | Parse route decorators statically to avoid calling the app factory in read-only mode. | high | methods=['none'] |
| /register | present-in-code | app/routes/*.py | Parse route decorators statically to avoid calling the app factory in read-only mode. | high | methods=['GET,POST'] |
| /report/download/pdf | missing-in-code | app/routes/*.py | Parse route decorators statically to avoid calling the app factory in read-only mode. | high | methods=['none'] |
| /report/generate | missing-in-code | app/routes/*.py | Parse route decorators statically to avoid calling the app factory in read-only mode. | high | methods=['none'] |
| /search/people | present-in-code | app/routes/*.py | Parse route decorators statically to avoid calling the app factory in read-only mode. | high | methods=['GET'] |

## source_of_truth_file

| missing_item | current_status | where_to_get_it | how_to_verify_it | confidence | notes |
| --- | --- | --- | --- | --- | --- |
| claude_brain_command | present | repo source of truth | Check whether .claude/commands/brain.md exists in the repo. | high | C:\Users\fedor\ibp\.claude\commands\brain.md |
| claude_log_command | present | repo source of truth | Check whether .claude/commands/log.md exists in the repo. | high | C:\Users\fedor\ibp\.claude\commands\log.md |
| claude_update_command | present | repo source of truth | Check whether .claude/commands/update.md exists in the repo. | high | C:\Users\fedor\ibp\.claude\commands\update.md |
| repo_claude | present | repo source of truth | Check whether CLAUDE.md exists in the repo. | high | C:\Users\fedor\ibp\CLAUDE.md |
| repo_current_state | present | repo source of truth | Check whether IBP_CURRENT_STATE.md exists in the repo. | high | C:\Users\fedor\ibp\IBP_CURRENT_STATE.md |
| repo_knowledge_export | present | repo source of truth | Check whether IBP_KNOWLEDGE_EXPORT.md exists in the repo. | high | C:\Users\fedor\ibp\IBP_KNOWLEDGE_EXPORT.md |
| repo_security_audit | present | repo source of truth | Check whether data/security_audit/AUDIT_REPORT.md exists in the repo. | high | C:\Users\fedor\ibp\data\security_audit\AUDIT_REPORT.md |

## tool_prerequisite

| missing_item | current_status | where_to_get_it | how_to_verify_it | confidence | notes |
| --- | --- | --- | --- | --- | --- |
| Holehe CLI | present | local PATH / Python scripts install | Run shutil.which('holehe') or the equivalent shell command. | high | C:\Users\fedor\AppData\Local\Programs\Python\Python312\Scripts\holehe.EXE |
| Maigret CLI | present | local PATH / Python scripts install | Run shutil.which('maigret') or the equivalent shell command. | high | C:\Users\fedor\AppData\Local\Programs\Python\Python312\Scripts\maigret.EXE |
| Mailcat CLI | missing | local PATH / Python scripts install | Run shutil.which('mailcat') or the equivalent shell command. | high | mailcat not found on PATH |
| Playwright browser cache | present | local Playwright browser install | Check the Windows Playwright browser cache directory. | medium | C:\Users\fedor\AppData\Local\ms-playwright |
| Sherlock CLI | present | local PATH / Python scripts install | Run shutil.which('sherlock') or the equivalent shell command. | high | C:\Users\fedor\AppData\Local\Programs\Python\Python312\Scripts\sherlock.EXE |
| Snoop CLI | missing | local PATH / Python scripts install | Run shutil.which('snoop') or the equivalent shell command. | high | snoop not found on PATH |

## vault_reference

| missing_item | current_status | where_to_get_it | how_to_verify_it | confidence | notes |
| --- | --- | --- | --- | --- | --- |
| 02 - Stirlitz/Dev Logs | present | Obsidian Stirlitz vault | Check whether the path referenced by .claude commands exists: C:\Users\fedor\Documents\Fedor's Brain\02 - Stirlitz\Dev Logs | high | Referenced by: C:\Users\fedor\ibp\.claude\commands\brain.md, C:\Users\fedor\ibp\.claude\commands\log.md |
| 02 - Stirlitz/Dev Workflow/Debugging Guide.md | present | Obsidian Stirlitz vault | Check whether the path referenced by .claude commands exists: C:\Users\fedor\Documents\Fedor's Brain\02 - Stirlitz\Dev Workflow\Debugging Guide.md | high | Referenced by: C:\Users\fedor\ibp\.claude\commands\log.md |
| 02 - Stirlitz/Roadmap/Active TODOs.md | present | Obsidian Stirlitz vault | Check whether the path referenced by .claude commands exists: C:\Users\fedor\Documents\Fedor's Brain\02 - Stirlitz\Roadmap\Active TODOs.md | high | Referenced by: C:\Users\fedor\ibp\.claude\commands\brain.md |
| 02 - Stirlitz/Stirlitz HQ.md | present | Obsidian Stirlitz vault | Check whether the path referenced by .claude commands exists: C:\Users\fedor\Documents\Fedor's Brain\02 - Stirlitz\Stirlitz HQ.md | high | Referenced by: C:\Users\fedor\ibp\.claude\commands\brain.md |
| brain_root | present | local Obsidian vault path | Check whether the configured brain root exists at C:\Users\fedor\Documents\Fedor's Brain. | high | Configured via --brain-root. |
| latest_dev_log | present | 02 - Stirlitz/Dev Logs/ | Check that the dev log directory exists and contains at least one Markdown file. | high | directory=C:\Users\fedor\Documents\Fedor's Brain\02 - Stirlitz\Dev Logs; latest=2026-04-14.md |
