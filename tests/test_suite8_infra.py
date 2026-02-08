"""Suite 8: Startup Checks + Logging Verification."""
import time
import sys
import io
import os
import re
import glob
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run():
    results = []
    start = time.time()

    # --- Test 1: Parse server startup log ---
    try:
        log_path = os.path.join(BASE_DIR, "tests", "server_log.txt")
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            server_log = f.read()

        # Check startup checks output
        has_checks_header = "IBP STARTUP CHECKS" in server_log
        has_ok = "[OK]" in server_log
        has_separator = "==========" in server_log

        # Parse individual checks
        check_lines = [line.strip() for line in server_log.split('\n') if line.strip().startswith('[')]
        checks_found = len(check_lines)

        # Report VK token status
        vk_line = [l for l in check_lines if 'VK Token' in l]
        vk_status = vk_line[0] if vk_line else "not found"

        # Report database check
        db_line = [l for l in check_lines if 'Database' in l]
        db_status = db_line[0] if db_line else "not found"

        ok = has_checks_header and checks_found >= 5
        note = f"checks_found={checks_found}, vk={vk_status[:50]}, db={db_status[:50]}"
        icon = "PASS" if ok else "FAIL"
        results.append((icon, "Startup checks output", note))
        print(f"  [{icon}] Startup checks: {checks_found} checks found")
        for cl in check_lines:
            print(f"    {cl}")

    except Exception as e:
        results.append(("FAIL", "Startup checks output", str(e)))
        print(f"  [FAIL] Startup checks: {e}")

    # --- Test 2: Log file exists ---
    try:
        logs_dir = os.path.join(BASE_DIR, "logs")
        today = datetime.now().strftime('%Y%m%d')
        log_pattern = os.path.join(logs_dir, f"ibp_{today}.log")
        log_files = glob.glob(log_pattern)

        # Also check for any log files
        all_logs = glob.glob(os.path.join(logs_dir, "ibp_*.log"))

        ok = len(log_files) > 0 or len(all_logs) > 0
        note = f"today_log={len(log_files)}, total_logs={len(all_logs)}"
        icon = "PASS" if ok else "FAIL"
        results.append((icon, "Log file exists", note))
        print(f"  [{icon}] Log file: {note}")

        if log_files:
            log_file = log_files[0]
        elif all_logs:
            log_file = all_logs[-1]
        else:
            log_file = None

    except Exception as e:
        results.append(("FAIL", "Log file exists", str(e)))
        print(f"  [FAIL] Log file: {e}")
        log_file = None

    # --- Test 3: Log format ---
    if log_file:
        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()

            last_50 = lines[-50:] if len(lines) > 50 else lines

            # Check format: [timestamp] [LEVEL] [module] message
            # Or: timestamp - module - LEVEL - message
            formatted_lines = 0
            for line in last_50:
                line = line.strip()
                if not line:
                    continue
                # Check for structured format
                if re.match(r'\[\d{4}-\d{2}-\d{2}', line) or re.match(r'\d{4}-\d{2}-\d{2}', line):
                    formatted_lines += 1

            ok = formatted_lines >= min(5, len([l for l in last_50 if l.strip()]))
            note = f"lines={len(lines)}, last_50_formatted={formatted_lines}"
            icon = "PASS" if ok else "FAIL"
            results.append((icon, "Log format correct", note))
            print(f"  [{icon}] Log format: {note}")

            # Show sample log lines
            for line in last_50[-5:]:
                if line.strip():
                    print(f"    {line.strip()[:120]}")

        except Exception as e:
            results.append(("FAIL", "Log format", str(e)))
            print(f"  [FAIL] Log format: {e}")

    # --- Test 4: No sensitive data in logs ---
    if log_file:
        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                log_content = f.read()

            # Check for full phone numbers (10+ digits unmasked)
            full_phone = re.findall(r'(?<!\*)\+?\d{10,}(?!\*)', log_content)
            # Check for tokens (long hex strings not masked)
            full_tokens = re.findall(r'[a-f0-9]{30,}', log_content)
            # Check for passwords
            has_password = 'password=' in log_content.lower() or 'passwd=' in log_content.lower()

            # Check masked patterns are used
            has_masked = '***' in log_content or '...' in log_content

            # Filter out expected long hex strings (like investigation IDs which are 32 hex chars)
            suspicious_tokens = [t for t in full_tokens if len(t) > 40]

            ok = not has_password and len(suspicious_tokens) == 0
            note = f"full_phones={len(full_phone)}, suspicious_tokens={len(suspicious_tokens)}, has_password={has_password}, masked={has_masked}"
            icon = "PASS" if ok else "FAIL"
            results.append((icon, "No sensitive data in logs", note))
            print(f"  [{icon}] Sensitive data check: {note}")

            if suspicious_tokens:
                print(f"    Suspicious tokens found: {[t[:10] + '...' for t in suspicious_tokens[:3]]}")
            if full_phone:
                print(f"    Full phone numbers found: {full_phone[:3]}")

        except Exception as e:
            results.append(("FAIL", "No sensitive data in logs", str(e)))
            print(f"  [FAIL] Sensitive data check: {e}")

    # --- Test 5: Server is still running ---
    try:
        import urllib.request
        resp = urllib.request.urlopen("http://127.0.0.1:5000/api/vk/token-status", timeout=5)
        status = resp.getcode()
        ok = status == 200
        note = f"status={status}"
        icon = "PASS" if ok else "FAIL"
        results.append((icon, "Server still running", note))
        print(f"  [{icon}] Server still running: {note}")
    except Exception as e:
        results.append(("FAIL", "Server still running", str(e)))
        print(f"  [FAIL] Server still running: {e}")

    elapsed = time.time() - start
    passed = sum(1 for r in results if r[0] == "PASS")
    print(f"\n  Time: {elapsed:.1f}s")
    print(f"  Result: {passed}/{len(results)} passed")

    return passed == len(results)


if __name__ == "__main__":
    print("=" * 60)
    print("SUITE 8: STARTUP CHECKS + LOGGING VERIFICATION")
    print("=" * 60)
    success = run()
    sys.exit(0 if success else 1)
