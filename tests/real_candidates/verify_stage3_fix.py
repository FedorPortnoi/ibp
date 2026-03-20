"""Verify Stage 3 VK fix — run one candidate through live pipeline."""
import sys
import requests
import time
import json
import re
import warnings
import os
from datetime import datetime

warnings.filterwarnings('ignore')

BASE_URL = "https://shtirletzsled.ru"
CANDIDATE = {
    "full_name": "Стасюк Сергей Анатольевич",
    "date_of_birth": "1967-10-31",
    "inn": "233500829075",
}


def log(msg=''):
    try:
        sys.stdout.buffer.write((msg + '\n').encode('utf-8', errors='replace'))
        sys.stdout.buffer.flush()
    except Exception:
        pass


def get_password():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.env')
    with open(env_path) as f:
        for line in f:
            if line.startswith('IBP_PASSWORD='):
                return line.strip().split('=', 1)[1]
    return ''


def get_csrf(session, url):
    r = session.get(url, verify=False)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', r.text)
    if m:
        return m.group(1)
    m = re.search(r'name="csrf-token"\s+content="([^"]+)"', r.text)
    return m.group(1) if m else ''


def main():
    log(f"{'='*60}")
    log(f"STAGE 3 FIX VERIFICATION — {datetime.now().isoformat()}")
    log(f"Candidate: {CANDIDATE['full_name']}")
    log(f"DOB: {CANDIDATE['date_of_birth']} | INN: {CANDIDATE['inn']}")
    log(f"Server: {BASE_URL}")
    log(f"{'='*60}")

    password = get_password()
    session = requests.Session()

    # Login
    csrf = get_csrf(session, f"{BASE_URL}/login")
    r = session.post(f"{BASE_URL}/login", data={
        'password': password, 'csrf_token': csrf
    }, verify=False, allow_redirects=True)
    if '/login' in r.url:
        log("FATAL: Login failed")
        return
    log("Logged in")

    # Submit candidate
    csrf = get_csrf(session, f"{BASE_URL}/candidate/history")
    form_data = {
        'full_name': CANDIDATE['full_name'],
        'date_of_birth': CANDIDATE['date_of_birth'],
        'inn': CANDIDATE['inn'],
        'csrf_token': csrf,
    }
    log("Submitting to pipeline...")
    r = session.post(f"{BASE_URL}/candidate/start", data=form_data,
                     verify=False, allow_redirects=True)

    if '/candidate/progress/' not in r.url:
        log(f"FATAL: Pipeline didn't start. URL: {r.url}")
        log(f"Response: {r.text[:500]}")
        return

    task_id = r.url.split('/candidate/progress/')[-1].rstrip('/')
    log(f"Pipeline started: task_id={task_id}")

    # Poll progress
    status_url = f"{BASE_URL}/candidate/progress/{task_id}/status"
    max_wait = 600
    elapsed = 0
    last_stage = ''
    check_id = None
    stage3_messages = []

    while elapsed < max_wait:
        try:
            pr = session.get(status_url, verify=False)
            if pr.status_code == 200:
                data = pr.json()
                current_stage = data.get('current_stage', '')
                percent = data.get('percent_complete', 0)
                status = data.get('status', '')
                check_id = data.get('check_id', check_id)
                msgs = data.get('messages', [])

                if current_stage != last_stage:
                    latest = msgs[-1] if msgs else ''
                    if isinstance(latest, dict):
                        latest = latest.get('text', str(latest))
                    log(f"  [{percent:3.0f}%] {current_stage} -- {latest}")
                    last_stage = current_stage

                # Capture stage 3 messages
                if 'social' in current_stage.lower():
                    for m in msgs:
                        txt = m.get('text', str(m)) if isinstance(m, dict) else str(m)
                        if txt not in [str(x) for x in stage3_messages]:
                            stage3_messages.append(m)

                if status == 'complete':
                    log("  Pipeline complete!")
                    break
                elif status == 'error':
                    log(f"  Pipeline error: {data.get('error', '?')}")
                    return
        except Exception as e:
            log(f"  Poll error: {e}")

        time.sleep(5)
        elapsed += 5

    if elapsed >= max_wait:
        log("TIMEOUT")
        return

    # Get final check_id
    if not check_id:
        try:
            final = session.get(status_url, verify=False).json()
            check_id = final.get('check_id', '')
        except:
            pass

    if not check_id:
        log("ERROR: No check_id")
        return

    log(f"\ncheck_id={check_id}")

    # Try JSON export
    log("Fetching JSON export...")
    jr = session.get(f"{BASE_URL}/candidate/export/{check_id}/json", verify=False)
    dossier = None
    if jr.status_code == 200:
        try:
            dossier = jr.json()
        except:
            pass

    # Try HTML dossier as fallback
    log("Fetching HTML dossier...")
    hr = session.get(f"{BASE_URL}/candidate/dossier/{check_id}", verify=False)
    html = hr.text if hr.status_code == 200 else ''

    log(f"\n{'='*60}")
    log("STAGE 3 RESULTS")
    log(f"{'='*60}")

    vk_count = 0
    tg_count = 0
    profiles_found = []

    if dossier:
        log("Source: JSON export")
        social = dossier.get('social_media_profiles', [])
        if isinstance(social, str):
            try:
                social = json.loads(social)
            except:
                social = []
        for p in (social or []):
            platform = p.get('platform', '?')
            if platform == 'vk':
                vk_count += 1
            elif platform == 'telegram':
                tg_count += 1
            display = p.get('display_name', '')
            if not display:
                display = (str(p.get('first_name', '')) + ' ' + str(p.get('last_name', ''))).strip()
            url = p.get('url', p.get('profile_url', ''))
            conf = p.get('confidence', p.get('confidence_score', ''))
            profiles_found.append((platform, display, url, conf))
    else:
        log("Source: HTML dossier (JSON export unavailable)")
        # Parse social section from HTML
        soc_match = re.search(r'Социальные сети.*?(\d+)\s*профил', html, re.DOTALL)
        if soc_match:
            total_social = int(soc_match.group(1))
            log(f"  HTML reports {total_social} profiles")
        # Find VK links
        vk_links = re.findall(r'vk\.com/[a-zA-Z0-9_.]+', html)
        vk_count = len(set(vk_links))
        # Find profile cards
        profile_cards = re.findall(r'\[([vk|telegram|ok]+)\]\s*([^|]+)\|([^|]*)\|([^\n<]*)', html)
        for pc in profile_cards:
            profiles_found.append(pc)

    log(f"\n  VK profiles found:       {vk_count}")
    log(f"  Telegram profiles found: {tg_count}")
    log(f"  Total profiles:          {vk_count + tg_count}")

    if profiles_found:
        log(f"\n  First profiles:")
        for i, (plat, name, url, conf) in enumerate(profiles_found[:5]):
            log(f"    {i+1}. [{plat}] {name} | {url} | confidence={conf}")

    # Stage 3 messages from polling
    if stage3_messages:
        log(f"\n  Stage 3 messages captured during polling:")
        for m in stage3_messages[-10:]:
            txt = m.get('text', str(m)) if isinstance(m, dict) else str(m)
            log(f"    {txt}")

    # Risk level
    if dossier:
        risk = dossier.get('risk_assessment', {})
        log(f"\n  Risk: {risk.get('risk_level', '?')} ({risk.get('risk_level_display', '?')})")
        log(f"  Red flags: {risk.get('red_flag_count', 0)}")

    # Final verdict
    log(f"\n{'='*60}")
    if vk_count > 0:
        log(f"RESULT: PASS — Stage 3 found {vk_count} VK profile(s)")
        log("The name order fix is WORKING.")
    elif tg_count > 0:
        log(f"RESULT: PARTIAL — Found {tg_count} Telegram but 0 VK profiles")
        log("Name fix may work but VK web token or API issue persists.")
    else:
        log("RESULT: FAIL — Stage 3 still found 0 profiles")
        log("The fix did not resolve the issue. Check server logs.")
    log(f"{'='*60}")


if __name__ == '__main__':
    main()
