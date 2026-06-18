from __future__ import annotations

import argparse
import ast
import importlib
import json
import os
import re
import shutil
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

DEFAULT_BRAIN_ROOT = Path(r"C:\Users\fedor\Documents\Fedor's Brain")
DEFAULT_PREFIX = "runtime_gap_audit"
PATH_RE = re.compile(r"(02 - Stirlitz/[A-Za-z0-9 _&()'\-./]+(?:\.md|/))")


@dataclass(frozen=True)
class Finding:
    missing_item: str
    category: str
    current_status: str
    where_to_get_it: str
    how_to_verify_it: str
    confidence: str
    notes: str


ENV_SPECS = [
    ("SECRET_KEY", True, "local .env or host secret manager", "required for app startup"),
    ("FLASK_ENV", True, "local .env or host environment", "selects config profile"),
    ("ENABLE_PEOPLE_SEARCH", False, "local .env or host environment", "feature flag"),
    ("DATABASE_URL", False, "local .env or host environment", "optional; SQLite fallback exists"),
    ("IBP_SESSION_TIMEOUT", False, "local .env or host environment", "optional timeout override"),
    ("IBP_SESSION_REMEMBER", False, "local .env or host environment", "optional remember-me override"),
    ("VK_USER_TOKEN", False, "VK OAuth or secret store", "VK user token"),
    ("VK_TOKEN", False, "legacy .env or secret store", "legacy VK token alias"),
    ("VK_SERVICE_TOKEN", False, "VK dashboard or secret store", "VK service token"),
    ("VK_LOGIN", False, "local .env only", "VK browser-login prerequisite"),
    ("VK_LOGIN_EMAIL", False, "local .env only", "VK browser-login prerequisite"),
    ("VK_PASSWORD", False, "local .env only", "VK browser-login prerequisite"),
    ("TELEGRAM_API_ID", False, "my.telegram.org or secret store", "Telethon credential"),
    ("TELEGRAM_API_HASH", False, "my.telegram.org or secret store", "Telethon credential"),
    ("TELEGRAM_PHONE", False, "local .env only", "Telethon phone"),
    ("ANTHROPIC_API_KEY", False, "Anthropic dashboard or secret store", "Claude integration key"),
    ("SEARCH4FACES_API_KEY", False, "provider dashboard or secret store", "face-search API key"),
    ("HUNTER_API_KEY", False, "Hunter dashboard or secret store", "Hunter API key"),
    ("RESEND_API_KEY", False, "Resend dashboard or secret store", "email delivery key"),
    ("FSSP_API_TOKEN", False, "FSSP provider account or secret store", "official FSSP token"),
    ("ENABLE_GEO_RESTRICTED_CHECKERS", False, "local .env or host environment", "geo-restricted sources flag"),
    ("GETCONTACT_API_URL", False, "GetContact partner docs or secret store", "GetContact API mode"),
    ("GETCONTACT_API_KEY", False, "GetContact dashboard or secret store", "GetContact API mode"),
    ("GETCONTACT_PARTNER_ID", False, "GetContact dashboard or secret store", "GetContact API mode"),
    ("GETCONTACT_HMAC_SECRET", False, "GetContact dashboard or secret store", "GetContact API mode"),
    ("LEAKCHECK_API_KEY", False, "LeakCheck dashboard or secret store", "paid LeakCheck"),
    ("DEHASHED_USERNAME", False, "DeHashed dashboard or secret store", "DeHashed credential"),
    ("DEHASHED_API_KEY", False, "DeHashed dashboard or secret store", "DeHashed credential"),
    ("DEHASHED_API_SECRET", False, "DeHashed dashboard or secret store", "DeHashed credential"),
    ("SNUSBASE_API_KEY", False, "Snusbase dashboard or secret store", "Snusbase credential"),
    ("HIBP_API_KEY", False, "HIBP dashboard or secret store", "HIBP paid mode"),
    ("MAILCAT_API_KEY", False, "provider docs or secret store", "Mailcat integration if adopted"),
]

FILES = [
    ("dotenv_file", ".env", "local repo root", "check whether the repo-local .env file exists", "values stay masked"),
    ("primary_db", "ibp_investigations.db", "local runtime data directory or deployment snapshot", "check whether the primary SQLite DB exists", "read-only SQLite probe runs separately"),
    ("telethon_session", "tg_session/ibp_session.session", "run scripts/auth_telegram.py interactively on the owner machine", "check whether the Telethon session exists", "required for Telegram Method C"),
    ("vk_state_cache", "vk_session/state.json", "populate via the local VK login flow", "check whether the VK state cache exists", "presence does not prove freshness"),
    ("vk_web_token_cache", "vk_session/web_token.json", "populate via the local VK login flow", "check whether the VK web-token cache exists", "presence does not prove freshness"),
    ("local_leak_db", "data/leaks/all_leaks.db", "local data snapshot / internal dataset location", "check whether the local leak DB exists", "absence blocks leak-db-backed sources"),
    ("demo_getcontact_data", "data/demo/getcontact_demo.jsonl", "already in repo demo data", "check whether the demo GetContact dataset exists", "demo fallback asset"),
    ("demo_telco_data", "data/demo/telco_demo.csv", "already in repo demo data", "check whether the demo telco dataset exists", "demo fallback asset"),
    ("demo_vk2012_data", "data/demo/vk_2012_demo.csv", "already in repo demo data", "check whether the demo VK 2012 dataset exists", "demo fallback asset"),
]

SOURCE_FILES = [
    ("repo_claude", "CLAUDE.md"),
    ("repo_current_state", "IBP_CURRENT_STATE.md"),
    ("repo_knowledge_export", "IBP_KNOWLEDGE_EXPORT.md"),
    ("repo_security_audit", "data/security_audit/AUDIT_REPORT.md"),
    ("claude_brain_command", ".claude/commands/brain.md"),
    ("claude_log_command", ".claude/commands/log.md"),
    ("claude_update_command", ".claude/commands/update.md"),
]

ROUTES = [
    "/health", "/login", "/register", "/candidate/new", "/candidate/start", "/candidate/history",
    "/candidate/progress/<task_id>/status", "/report/generate", "/report/download/pdf",
    "/phase2/api/sources/status", "/phase2/api/telegram/status", "/search/people",
]

TOOLS = [("holehe", "Holehe CLI"), ("mailcat", "Mailcat CLI"), ("maigret", "Maigret CLI"), ("sherlock", "Sherlock CLI"), ("snoop", "Snoop CLI")]


def add(item, category, status, where, verify, confidence, notes):
    return Finding(item, category, status, where, verify, confidence, notes)


def parse_args():
    p = argparse.ArgumentParser(description="Read-only local audit for missing prerequisites and unresolved runtime truth gaps.")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--brain-root", default=str(DEFAULT_BRAIN_ROOT))
    p.add_argument("--env-file", default=".env")
    p.add_argument("--output-dir", default="artifacts")
    p.add_argument("--report-prefix", default=DEFAULT_PREFIX)
    return p.parse_args()


def resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def read_env_file(path: Path) -> dict[str, str]:
    data = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        data[key] = value.strip().strip('"').strip("'")
    return data


def seed_env(values: dict[str, str]) -> None:
    for key, value in values.items():
        os.environ.setdefault(key, value)


def env_value(values: dict[str, str], key: str) -> str | None:
    return os.environ.get(key) or values.get(key)


def boolish(value: str | None):
    if value is None:
        return None
    text = value.strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None

def env_findings(values: dict[str, str]) -> list[Finding]:
    findings = []
    dotenv_keys = set(values)
    for key, required, where, note in ENV_SPECS:
        sources = []
        if os.environ.get(key):
            sources.append("process-env")
        if key in dotenv_keys:
            sources.append("dotenv-file")
        if sources:
            status = "local-present"
        elif required:
            status = "local-missing"
        else:
            status = "optional"
        findings.append(add(key, "environment_variable", status, where, f"Check effective local runtime environment and .env for {key}.", "high", f"{note}. Presence only; value masked. Sources={', '.join(sources) if sources else 'none'}."))
    return findings


def file_findings(repo_root: Path) -> list[Finding]:
    findings = []
    for name, rel, where, verify, note in FILES:
        path = repo_root / rel
        status = "present" if path.exists() else "missing"
        extra = f"path={path}"
        if path.exists() and path.is_file():
            try:
                extra += f" size={path.stat().st_size}"
            except OSError:
                pass
        findings.append(add(name, "file_prerequisite", status, where, verify, "high", f"{note}; {extra}"))
    return findings


def sqlite_finding(path: Path, item: str) -> Finding:
    if not path.exists():
        return add(item, "database", "missing", "local runtime data directory or deployment snapshot", f"Open SQLite at {path} in read-only mode and run PRAGMA quick_check.", "high", f"SQLite file not found at {path}")
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute("PRAGMA quick_check;")
        quick = cur.fetchone()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = [row[0] for row in cur.fetchall()]
        conn.close()
    except Exception as exc:
        return add(item, "database", "unreadable", "local runtime data directory", f"Open SQLite at {path} in read-only mode and run PRAGMA quick_check.", "high", f"read-only open failed: {exc}")
    result = quick[0] if quick else "unknown"
    return add(item, "database", "readable" if result == "ok" else "needs-review", "already local", "Open the SQLite file read-only and run PRAGMA quick_check plus a table inventory.", "high", f"quick_check={result}; tables={len(tables)}; sample={', '.join(tables[:8]) if tables else 'none'}")


def source_file_findings(repo_root: Path) -> list[Finding]:
    return [add(name, "source_of_truth_file", "present" if (repo_root / rel).exists() else "missing", "repo source of truth", f"Check whether {rel} exists in the repo.", "high", str(repo_root / rel)) for name, rel in SOURCE_FILES]


def vault_findings(repo_root: Path, brain_root: Path) -> list[Finding]:
    findings = [add("brain_root", "vault_reference", "present" if brain_root.exists() else "missing", "local Obsidian vault path", f"Check whether the configured brain root exists at {brain_root}.", "high", "Configured via --brain-root." )]
    logs_dir = brain_root / "02 - Stirlitz" / "Dev Logs"
    latest = None
    if logs_dir.exists():
        logs = sorted(logs_dir.glob("*.md"))
        latest = logs[-1].name if logs else None
    findings.append(add("latest_dev_log", "vault_reference", "present" if latest else "missing", "02 - Stirlitz/Dev Logs/", "Check that the dev log directory exists and contains at least one Markdown file.", "high", f"directory={logs_dir}; latest={latest or 'none'}"))
    refs: dict[str, set[str]] = defaultdict(set)
    for command_path in sorted((repo_root / ".claude" / "commands").rglob("*.md")):
        try:
            text = command_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in PATH_RE.finditer(text):
            refs[match.group(1).rstrip("/")].add(str(command_path))
    for rel, sources in sorted(refs.items()):
        path = brain_root / rel
        findings.append(add(rel, "vault_reference", "present" if path.exists() else "missing", "Obsidian Stirlitz vault", f"Check whether the path referenced by .claude commands exists: {path}", "high", f"Referenced by: {', '.join(sorted(sources))}"))
    return findings


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def import_status(module_name: str, repo_root: Path) -> tuple[bool, str]:
    original = list(sys.path)
    try:
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        importlib.import_module(module_name)
        return True, "import-ok"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        sys.path[:] = original


def import_findings(repo_root: Path) -> list[Finding]:
    findings = []
    for module_name in ("config", "app"):
        ok, message = import_status(module_name, repo_root)
        findings.append(add(f"{module_name}_import", "runtime_readiness", "import-ok" if ok else "import-failed", f"{module_name}.py / package in repo", f"Import {module_name} with bytecode writes disabled.", "high", message))
    return findings


def create_app_finding(app_init: Path) -> Finding:
    try:
        tree = ast.parse(app_init.read_text(encoding="utf-8"), filename=str(app_init))
    except Exception as exc:
        return add("create_app_factory", "runtime_readiness", "unknown", "app/__init__.py", "Inspect the app factory for write-side effects before calling it from a read-only audit.", "medium", f"parse failed: {exc}")
    func = next((node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "create_app"), None)
    if func is None:
        return add("create_app_factory", "runtime_readiness", "missing", "app/__init__.py", "Confirm that create_app is defined in app/__init__.py.", "high", "No create_app function found")
    side_effects = []
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            name = dotted_name(node.func)
            if name in {"db.create_all", "db.session.commit", "os.makedirs"} or name.startswith("_migrate_"):
                side_effects.append(name)
    if side_effects:
        return add("create_app_factory", "runtime_readiness", "unsafe-to-auto-run-read-only", "app/__init__.py", "Review create_app statically; only execute it intentionally if write-side effects are acceptable.", "high", f"Detected side effects: {', '.join(sorted(set(side_effects)))}")
    return add("create_app_factory", "runtime_readiness", "safe-to-auto-run", "app/__init__.py", "Review create_app statically before execution.", "high", "No obvious write-side effects detected")

def config_findings(values: dict[str, str], repo_root: Path) -> list[Finding]:
    seed_env(values)
    ok, message = import_status("config", repo_root)
    if not ok:
        return [add("config_flags", "runtime_readiness", "unknown", "config.py", "Import config.py safely and inspect effective defaults.", "medium", f"config import failed: {message}")]
    config_module = sys.modules.get("config")
    config_map = getattr(config_module, "config", {})
    default_cfg = config_map.get("default") if isinstance(config_map, dict) else None
    flags = {
        "SESSION_COOKIE_SECURE": getattr(default_cfg, "SESSION_COOKIE_SECURE", None),
        "SESSION_COOKIE_HTTPONLY": getattr(default_cfg, "SESSION_COOKIE_HTTPONLY", None),
        "SESSION_COOKIE_SAMESITE": getattr(default_cfg, "SESSION_COOKIE_SAMESITE", None),
        "ENABLE_PEOPLE_SEARCH": boolish(env_value(values, "ENABLE_PEOPLE_SEARCH")),
        "ENABLE_GEO_RESTRICTED_CHECKERS": boolish(env_value(values, "ENABLE_GEO_RESTRICTED_CHECKERS")),
        "DEMO_MODE_PREDICTED": not bool(env_value(values, "VK_SERVICE_TOKEN")),
    }
    return [add(name, "runtime_readiness", "known" if value is not None else "unknown", "config.py and effective local env", f"Inspect config.py and local env handling for {name}.", "high" if value is not None else "medium", f"Derived value={value!r}") for name, value in flags.items()]


def route_manifest(routes_root: Path) -> dict[str, set[str]]:
    manifest: dict[str, set[str]] = defaultdict(set)
    for path in sorted(routes_root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if dotted_name(decorator.func).split(".")[-1] != "route":
                    continue
                route = None
                methods = []
                if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
                    route = decorator.args[0].value
                for kw in decorator.keywords:
                    if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                        for item in kw.value.elts:
                            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                                methods.append(item.value)
                if route:
                    manifest[route].add(",".join(methods) if methods else "GET")
    return manifest


def route_findings(repo_root: Path) -> list[Finding]:
    manifest = route_manifest(repo_root / "app" / "routes")
    return [add(route, "runtime_route", "present-in-code" if manifest.get(route) else "missing-in-code", "app/routes/*.py", "Parse route decorators statically to avoid calling the app factory in read-only mode.", "high", f"methods={sorted(manifest.get(route, [])) or ['none']}") for route in ROUTES]


def tool_findings() -> list[Finding]:
    findings = [add(label, "tool_prerequisite", "present" if shutil.which(cmd) else "missing", "local PATH / Python scripts install", f"Run shutil.which('{cmd}') or the equivalent shell command.", "high", shutil.which(cmd) or f"{cmd} not found on PATH") for cmd, label in TOOLS]
    cache = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    findings.append(add("Playwright browser cache", "tool_prerequisite", "present" if cache.exists() else "missing", "local Playwright browser install", "Check the Windows Playwright browser cache directory.", "medium", str(cache)))
    return findings


INTEGRATIONS = [
    {"name": "VK user token", "code": ["app/utils/vk_token_manager.py", "app/services/phase1/buratino_vk_search.py"], "env": ["VK_USER_TOKEN", "VK_TOKEN"], "where": "VK OAuth flow or secret store", "verify": "Confirm local token presence, then run one safe manual VK API probe.", "notes": "Presence only; validity still needs a manual check."},
    {"name": "VK service token", "code": ["app/utils/vk_token_manager.py", "app/services/phase1/vk_web_search.py"], "env": ["VK_SERVICE_TOKEN"], "files": ["vk_session/state.json", "vk_session/web_token.json"], "where": "VK dashboard or secret store", "verify": "Confirm env presence and caches, then run one safe manual VK probe.", "dashboard": True, "notes": "Missing service token usually leaves VK service flows in demo mode."},
    {"name": "Telethon session", "code": ["app/services/telegram/session_manager.py"], "env": ["TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_PHONE"], "files": ["tg_session/ibp_session.session"], "where": "Run scripts/auth_telegram.py interactively on the owner machine", "verify": "Confirm creds plus session file, then use a local status endpoint or one-shot health check manually."},
    {"name": "OpenSanctions", "code": ["app/services/candidate/opensanctions_service.py"], "where": "no local secret expected", "verify": "Run a one-shot dummy-name check manually because external auth/reachability can drift.", "notes": "Local config-free, but still depends on upstream behavior."},
    {"name": "Claude / Anthropic", "code": ["app/services/ai/claude_integration.py"], "env": ["ANTHROPIC_API_KEY"], "where": "Anthropic dashboard or secret store", "verify": "Confirm local key presence, then verify only if the code path is re-enabled.", "dashboard": True, "notes": "Key presence does not override the current hard-disabled code path."},
    {"name": "Resend email", "code": ["app/services/email_service.py"], "env": ["RESEND_API_KEY"], "where": "Resend dashboard or secret store", "verify": "Confirm key presence locally, then use a non-billable or explicitly approved manual email test.", "dashboard": True},
    {"name": "Hunter.io", "code": ["app/services/phase2/email_sources.py"], "env": ["HUNTER_API_KEY"], "where": "Hunter dashboard or secret store", "verify": "Confirm key presence locally, then use an approved low-volume manual probe.", "dashboard": True},
    {"name": "Search4Faces API", "code": ["app/services/phase2/search4faces_service.py"], "env": ["SEARCH4FACES_API_KEY"], "where": "provider dashboard or secret store", "verify": "Confirm key presence locally, then run manual verification with approved test media.", "dashboard": True},
    {"name": "FSSP API / site path", "code": ["app/services/phase3/fssp_search.py"], "env": ["FSSP_API_TOKEN", "ENABLE_GEO_RESTRICTED_CHECKERS"], "where": "FSSP account, local env, and Russian-host runtime", "verify": "Confirm local token/flag, then verify from the production or Russian host with a safe manual check.", "dashboard": True, "prod": True},
    {"name": "Geo-restricted checkers", "code": ["app/services/phase2/forgot_password_oracle.py", "app/services/phase3/passport_check.py"], "env": ["ENABLE_GEO_RESTRICTED_CHECKERS"], "where": "production/Russian host access plus local env toggle", "verify": "Verify only from the production-compatible host with explicitly approved manual checks.", "prod": True},
    {"name": "GetContact real API", "code": ["app/services/phase2/sources/getcontact.py"], "env": ["GETCONTACT_API_URL", "GETCONTACT_API_KEY", "GETCONTACT_PARTNER_ID", "GETCONTACT_HMAC_SECRET"], "where": "GetContact partner dashboard or secret store", "verify": "Confirm local keys, then run an approved low-volume manual probe.", "dashboard": True},
    {"name": "LeakCheck paid mode", "code": ["app/services/phase2/sources/breach_api.py"], "env": ["LEAKCHECK_API_KEY"], "where": "LeakCheck dashboard or secret store", "verify": "Confirm the key locally, then run a single approved manual lookup.", "dashboard": True},
    {"name": "DeHashed", "code": ["app/services/phase2/sources/breach_api.py"], "env": ["DEHASHED_USERNAME", "DEHASHED_API_KEY", "DEHASHED_API_SECRET"], "where": "DeHashed dashboard or secret store", "verify": "Confirm credentials locally, then verify with a single approved lookup after the stubbed code is implemented.", "dashboard": True, "notes": "Code path is currently stubbed/TODO."},
    {"name": "Snusbase", "code": ["app/services/phase2/sources/breach_api.py"], "env": ["SNUSBASE_API_KEY"], "where": "Snusbase dashboard or secret store", "verify": "Confirm the key locally, then verify with an approved lookup after the stubbed code is implemented.", "dashboard": True, "notes": "Code path is currently stubbed/TODO."},
    {"name": "HIBP paid API", "code": ["app/services/phase2/sources/breach_api.py"], "env": ["HIBP_API_KEY"], "where": "HIBP dashboard or secret store", "verify": "Confirm the key locally, then verify with a single approved lookup after the paid path is implemented.", "dashboard": True},
    {"name": "Local leak DB sources", "code": ["app/services/phase2/sources/leak_sources.py"], "files": ["data/leaks/all_leaks.db"], "where": "internal/local data snapshot", "verify": "Confirm the SQLite file exists and opens read-only, then verify schema and source coverage manually."},
    {"name": "Mailcat", "code": ["app/services/phase2/mailcat_discovery.py"], "cmd": ["mailcat"], "env": ["MAILCAT_API_KEY"], "where": "local tool install and any related provider config", "verify": "Confirm the CLI is on PATH and any needed config exists locally before manual verification."},
    {"name": "Maigret CLI", "code": ["app/services/maigret_search.py"], "cmd": ["maigret"], "where": "local Python environment / PATH", "verify": "Confirm the CLI is on PATH and run a deliberately approved username check manually."},
    {"name": "Sherlock CLI", "code": ["app/services/sherlock_search.py"], "cmd": ["sherlock"], "where": "local Python environment / PATH", "verify": "Confirm the CLI is on PATH and run a deliberately approved username check manually."},
    {"name": "Snoop CLI", "code": ["app/services/snoop_search.py"], "cmd": ["snoop"], "where": "local tool install / PATH", "verify": "Confirm the CLI is on PATH and any required dataset/setup exists before manual verification."},
    {"name": "Playwright / Chromium", "code": ["app/routes/candidate_check.py", "app/templates/candidate_dossier_pdf.html"], "where": "local Python package plus Playwright browser install", "verify": "Confirm the playwright module imports and browsers are installed before manual export verification.", "notes": "This tool checks local package/browser-cache presence only; it does not launch a browser."},
]


def integration_findings(repo_root: Path, values: dict[str, str]) -> list[Finding]:
    findings = []
    for spec in INTEGRATIONS:
        code_present = all((repo_root / p).exists() for p in spec.get("code", []))
        present_env = [k for k in spec.get("env", []) if env_value(values, k)]
        missing_env = [k for k in spec.get("env", []) if k not in present_env]
        present_files = [p for p in spec.get("files", []) if (repo_root / p).exists()]
        missing_files = [p for p in spec.get("files", []) if p not in present_files]
        present_cmd = [c for c in spec.get("cmd", []) if shutil.which(c)]
        missing_cmd = [c for c in spec.get("cmd", []) if c not in present_cmd]
        labels = ["code-present" if code_present else "code-missing"]
        if not missing_env and not missing_files and not missing_cmd:
            labels.append("configured-locally")
        else:
            blockers = []
            if missing_env:
                blockers.append("secret")
            if missing_files:
                blockers.append("session-or-file")
            if missing_cmd:
                blockers.append("tooling")
            labels.append(f"blocked-by-missing-{'-'.join(blockers)}")
        if spec.get("dashboard"):
            labels.append("needs-dashboard-access")
        if spec.get("prod"):
            labels.append("needs-production-host-access")
        labels.append("needs-safe-manual-verification")
        notes = [spec.get("notes", ""), f"env_present={present_env or ['none']}", f"env_missing={missing_env or ['none']}", f"files_present={present_files or ['none']}", f"files_missing={missing_files or ['none']}", f"commands_present={present_cmd or ['none']}", f"commands_missing={missing_cmd or ['none']}"]
        findings.append(add(spec["name"], "integration_readiness", "; ".join(labels), spec["where"], spec["verify"], "high" if code_present else "medium", " ".join(part for part in notes if part)))
    return findings

def summarize(findings: list[Finding]) -> dict[str, object]:
    categories = Counter(f.category for f in findings)
    statuses = Counter(f.current_status for f in findings)
    missing_like = sum(1 for f in findings if any(token in f.current_status for token in ("missing", "blocked", "unsafe-to-auto-run-read-only", "import-failed", "unreadable")))
    return {
        "total_findings": len(findings),
        "category_counts": dict(sorted(categories.items())),
        "status_counts": dict(sorted(statuses.items())),
        "missing_like_findings": missing_like,
    }


def write_reports(json_path: Path, md_path: Path, metadata: dict[str, object], summary: dict[str, object], findings: list[Finding]) -> None:
    payload = {"metadata": metadata, "summary": summary, "findings": [asdict(f) for f in findings]}
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    by_cat: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        by_cat[finding.category].append(finding)
    lines = [
        "# Runtime Gap Audit",
        "",
        "## Metadata",
        f"- generated_at: `{metadata['generated_at']}`",
        f"- repo_root: `{metadata['repo_root']}`",
        f"- brain_root: `{metadata['brain_root']}`",
        f"- env_file: `{metadata['env_file']}`",
        f"- report_prefix: `{metadata['report_prefix']}`",
        "",
        "## Summary",
        f"- total_findings: `{summary['total_findings']}`",
        f"- missing_like_findings: `{summary['missing_like_findings']}`",
        f"- categories: `{json.dumps(summary['category_counts'], ensure_ascii=False, sort_keys=True)}`",
        "",
    ]
    for category in sorted(by_cat):
        lines.append(f"## {category}")
        lines.append("")
        lines.append("| missing_item | current_status | where_to_get_it | how_to_verify_it | confidence | notes |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for finding in sorted(by_cat[category], key=lambda item: item.missing_item.lower()):
            row = [finding.missing_item, finding.current_status, finding.where_to_get_it, finding.how_to_verify_it, finding.confidence, finding.notes]
            lines.append("| " + " | ".join(part.replace("|", "\\|") for part in row) + " |")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = resolve(Path.cwd(), args.repo_root)
    brain_root = resolve(Path.cwd(), args.brain_root)
    env_file = resolve(repo_root, args.env_file)
    output_dir = resolve(repo_root, args.output_dir)
    values = read_env_file(env_file)
    seed_env(values)

    findings: list[Finding] = []
    findings.extend(env_findings(values))
    findings.extend(file_findings(repo_root))
    findings.append(sqlite_finding(repo_root / "ibp_investigations.db", "primary_db_readability"))
    findings.append(sqlite_finding(repo_root / "data" / "leaks" / "all_leaks.db", "local_leak_db_readability"))
    findings.extend(source_file_findings(repo_root))
    findings.extend(vault_findings(repo_root, brain_root))
    findings.extend(import_findings(repo_root))
    findings.append(create_app_finding(repo_root / "app" / "__init__.py"))
    findings.extend(config_findings(values, repo_root))
    findings.extend(route_findings(repo_root))
    findings.extend(tool_findings())
    findings.extend(integration_findings(repo_root, values))

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "brain_root": str(brain_root),
        "env_file": str(env_file),
        "report_prefix": args.report_prefix,
        "read_only_policy": "No external requests, no app-factory execution, no login/code-send flows, no DB writes, and no secret values emitted.",
    }
    summary = summarize(findings)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{args.report_prefix}.json"
    md_path = output_dir / f"{args.report_prefix}.md"
    write_reports(json_path, md_path, metadata, summary, findings)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Total findings: {summary['total_findings']}")
    print(f"Missing/blocking findings: {summary['missing_like_findings']}")
    print(f"Top statuses: {dict(Counter(f.current_status for f in findings).most_common(5))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
