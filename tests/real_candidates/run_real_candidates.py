"""
Run 5 real candidates through the IBP pipeline via the live web UI.
Log every stage's results — what's real, what's demo, what failed.
"""
import sys
import requests
import time
import json
import re
import warnings
import os
from datetime import datetime

warnings.filterwarnings('ignore')

# Dual output: write to both console and log file
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run_log.txt')
_log_file = None


def log(msg=''):
    """Print to both log file and stdout."""
    global _log_file
    if _log_file is None:
        _log_file = open(LOG_PATH, 'w', encoding='utf-8')
    _log_file.write(msg + '\n')
    _log_file.flush()
    try:
        sys.stdout.buffer.write((msg + '\n').encode('utf-8', errors='replace'))
        sys.stdout.buffer.flush()
    except Exception:
        pass


BASE_URL = "https://shtirletzsled.ru"


def get_password():
    """Read password from .env."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.env')
    with open(env_path) as f:
        for line in f:
            if line.startswith('IBP_PASSWORD='):
                return line.strip().split('=', 1)[1]
    return ''


PASSWORD = get_password()

CANDIDATES = [
    {
        "full_name": "Судин Артем Алексеевич",
        "date_of_birth": "1990-11-29",
        "inn": "232308435186",
        "passport": "0319 231799",
        "region": "Краснодарский край",
        "registered_address": "г. Абинск ул. Мира д. 222",
        "phone": "+79676573634",
        "email": "",
        "notes": "Known: 2015 admin arrest for fleeing car accident"
    },
    {
        "full_name": "Стасюк Сергей Анатольевич",
        "date_of_birth": "1967-10-31",
        "inn": "233500829075",
        "passport": "0312 107459",
        "region": "Краснодарский край",
        "registered_address": "г. Кореновск ул. Свободная д. 58",
        "phone": "+79186394054",
        "email": "",
        "notes": "HR says clean"
    },
    {
        "full_name": "Таячкова Марина Вячеславовна",
        "date_of_birth": "1980-10-30",
        "inn": "233501519037",
        "passport": "0325 380785",
        "region": "Краснодарский край",
        "registered_address": "г. Кореновск ул. Северная д. 14в",
        "phone": "+79183444368",
        "email": "",
        "notes": "Known: admin responsibility for refusing medical exam"
    },
    {
        "full_name": "Калмыков Александр Николаевич",
        "date_of_birth": "1960-03-19",
        "inn": "",
        "passport": "0305 711565",
        "region": "Краснодарский край",
        "registered_address": "г. Кореновск пер. Пролетарский д. 23",
        "phone": "+79183472072",
        "email": "",
        "notes": "No INN — tests pipeline with missing INN"
    },
    {
        "full_name": "Левченко Надежда Александровна",
        "date_of_birth": "1982-09-13",
        "inn": "233506450100",
        "passport": "0304 175553",
        "region": "Краснодарский край",
        "registered_address": "г. Кореновск ул. Пляжная д. 10а",
        "phone": "+79189321373",
        "email": "",
        "notes": "HR says clean"
    },
]


def get_csrf_token(session, url):
    """Extract CSRF token from any page."""
    r = session.get(url, verify=False)
    # Try hidden input first
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', r.text)
    if m:
        return m.group(1)
    # Try meta tag
    m = re.search(r'name="csrf-token"\s+content="([^"]+)"', r.text)
    if m:
        return m.group(1)
    return ''


def login(session):
    """Log in to IBP."""
    csrf_token = get_csrf_token(session, f"{BASE_URL}/login")

    r = session.post(f"{BASE_URL}/login", data={
        'password': PASSWORD,
        'csrf_token': csrf_token
    }, verify=False, allow_redirects=True)

    if '/login' in r.url:
        log("ERROR: Login failed!")
        return False
    log("Logged in successfully")
    return True


def run_candidate(session, candidate, index):
    """Run one candidate through the pipeline. Return full results."""
    name = candidate['full_name']
    log(f"\n{'='*70}")
    log(f"CANDIDATE {index}/5: {name}")
    log(f"DOB: {candidate['date_of_birth']} | INN: {candidate['inn'] or 'NONE'}")
    log(f"Notes: {candidate['notes']}")
    log(f"{'='*70}")

    result = {
        'candidate': name,
        'inn': candidate['inn'],
        'status': 'UNKNOWN',
        'error': None,
        'duration': 0,
        'stages': {},
        'dossier': {},
        'red_flags': [],
        'risk_level': '',
    }

    start = time.time()

    try:
        # Get CSRF from a page that extends base.html
        csrf = get_csrf_token(session, f"{BASE_URL}/candidate/history")

        # Build form data using the correct field names from routes/candidate_check.py
        form_data = {
            'full_name': candidate['full_name'],
            'date_of_birth': candidate['date_of_birth'],
            'csrf_token': csrf,
        }

        # INN is required — add if present
        if candidate['inn']:
            form_data['inn'] = candidate['inn']
        if candidate['passport']:
            form_data['passport'] = candidate['passport']
        if candidate['region']:
            form_data['region'] = candidate['region']
        if candidate['registered_address']:
            form_data['registered_address'] = candidate['registered_address']
        if candidate['phone']:
            form_data['phone'] = candidate['phone']
        if candidate['email']:
            form_data['email'] = candidate['email']

        log(f"  Submitting to pipeline...")
        r = session.post(f"{BASE_URL}/candidate/start", data=form_data,
                         verify=False, allow_redirects=True)

        if '/candidate/progress/' not in r.url:
            # Check for validation error
            if 'ИНН' in r.text:
                result['status'] = 'REJECTED'
                err_match = re.search(r'"error"[^>]*>(.*?)<', r.text, re.DOTALL)
                err_msg = err_match.group(1).strip() if err_match else 'INN validation error'
                result['error'] = err_msg
                result['duration'] = time.time() - start
                log(f"  REJECTED: {err_msg}")
                return result

            result['status'] = 'FAILED_TO_START'
            result['error'] = f"Unexpected URL: {r.url} (status {r.status_code})"
            result['duration'] = time.time() - start
            log(f"  Failed to start: {r.url}")
            return result

        # Extract task_id from URL
        progress_url = r.url
        task_id = progress_url.split('/candidate/progress/')[-1].split('/')[0].rstrip('/')
        log(f"  Pipeline started: task_id={task_id}")

        # Poll progress
        status_url = f"{BASE_URL}/candidate/progress/{task_id}/status"
        max_wait = 600  # 10 minutes max
        poll_interval = 5
        elapsed = 0
        last_stage = ''
        check_id = None

        while elapsed < max_wait:
            try:
                pr = session.get(status_url, verify=False)
                if pr.status_code == 200:
                    data = pr.json()

                    current_stage = data.get('current_stage', '')
                    percent = data.get('percent_complete', 0)
                    status = data.get('status', '')
                    check_id = data.get('check_id', check_id)

                    # Log stage transitions
                    if current_stage != last_stage:
                        msgs = data.get('messages', [])
                        latest_msg = msgs[-1] if msgs else ''
                        log(f"  [{percent:3.0f}%] {current_stage} -- {latest_msg}")
                        last_stage = current_stage

                    # Check completion
                    if status == 'complete':
                        log(f"  Pipeline complete!")
                        break
                    elif status == 'error':
                        result['status'] = 'PIPELINE_ERROR'
                        result['error'] = data.get('error', 'Unknown error')
                        result['duration'] = time.time() - start
                        log(f"  Pipeline error: {result['error'][:200]}")
                        return result
                    elif status == 'cancelled':
                        result['status'] = 'CANCELLED'
                        result['duration'] = time.time() - start
                        log(f"  Pipeline cancelled")
                        return result
                    elif status == 'awaiting_confirmation':
                        conf_url = data.get('confirmation_url', '')
                        if conf_url:
                            log(f"  Awaiting confirmation at {conf_url}")

            except Exception as e:
                log(f"  Poll error: {e}")

            time.sleep(poll_interval)
            elapsed += poll_interval

        if elapsed >= max_wait:
            result['status'] = 'TIMEOUT'
            result['error'] = f"Pipeline timed out after {max_wait}s"
            result['duration'] = time.time() - start
            log(f"  TIMEOUT after {max_wait}s")
            return result

        # Get check_id from final status poll
        if not check_id:
            try:
                final = session.get(status_url, verify=False).json()
                check_id = final.get('check_id', '')
            except:
                pass

        if check_id:
            log(f"  Fetching dossier (check_id={check_id})...")

            # Fetch JSON export
            json_url = f"{BASE_URL}/candidate/export/{check_id}/json"
            jr = session.get(json_url, verify=False)

            if jr.status_code == 200:
                try:
                    dossier_data = jr.json()
                except:
                    dossier_data = json.loads(jr.text)

                result['dossier'] = dossier_data
                result['status'] = 'COMPLETE'
                analyze_dossier(result, dossier_data, candidate)
            else:
                log(f"  JSON export returned {jr.status_code}")
                html_url = f"{BASE_URL}/candidate/dossier/{check_id}"
                hr = session.get(html_url, verify=False)
                if hr.status_code == 200:
                    result['status'] = 'COMPLETE_NO_JSON'
                    log(f"  Dossier HTML loaded ({len(hr.text)} bytes)")
                else:
                    result['status'] = 'DOSSIER_ERROR'
                    result['error'] = f"HTML={hr.status_code}, JSON={jr.status_code}"
        else:
            result['status'] = 'NO_CHECK_ID'
            result['error'] = "Could not determine check_id"
            log(f"  Could not get check_id")

        result['duration'] = time.time() - start

    except Exception as e:
        result['status'] = 'EXCEPTION'
        result['error'] = str(e)
        result['duration'] = time.time() - start
        log(f"  Exception: {e}")
        import traceback
        traceback.print_exc()

    return result


def analyze_dossier(result, data, candidate):
    """Analyze dossier data -- classify each section as REAL, DEMO, or EMPTY."""

    log(f"\n  --- DOSSIER ANALYSIS ---")

    meta = data.get('meta', {})
    log(f"  Check mode: {meta.get('check_mode', '?')}")
    log(f"  Duration: {meta.get('duration_seconds', '?')}s")
    log(f"  Sources checked: {meta.get('sources_checked', '?')}")
    log(f"  Sources with results: {meta.get('sources_with_results', '?')}")

    cand = data.get('candidate', {})
    risk = data.get('risk_assessment', {})
    log(f"  [Stage 0] Candidate: {cand.get('full_name')} | INN: {cand.get('inn')}")

    # Stage 1: Business Records
    biz = _ensure_list(data.get('business_records'))
    biz_sources = set(r.get('source', '') for r in biz) if biz else set()
    biz_type = classify_data(biz, biz_sources)
    log(f"  [Stage 1] Business: {len(biz)} records, sources={biz_sources}, type={biz_type}")
    for b in biz[:5]:
        log(f"    - {b.get('company_name', b.get('name', '?'))} | INN: {b.get('inn', '?')} | Role: {b.get('role', '?')} | Source: {b.get('source', '?')}")
    result['stages']['business'] = {'count': len(biz), 'sources': list(biz_sources), 'data_type': biz_type}

    # Stage 1: Court Records
    courts = _ensure_list(data.get('court_records'))
    court_sources = set(r.get('source', '') for r in courts) if courts else set()
    court_type = classify_data(courts, court_sources)
    log(f"  [Stage 1] Courts: {len(courts)} records, sources={court_sources}, type={court_type}")
    for c in courts[:5]:
        log(f"    - {c.get('case_number', '?')} | {str(c.get('court_name', '?'))[:50]} | {c.get('case_type', '?')} | Source: {c.get('source', '?')}")
    result['stages']['courts'] = {'count': len(courts), 'sources': list(court_sources), 'data_type': court_type}

    # Stage 1: FSSP
    fssp = _ensure_list(data.get('fssp_records'))
    fssp_sources = set(r.get('source', '') for r in fssp) if fssp else set()
    fssp_type = classify_data(fssp, fssp_sources)
    log(f"  [Stage 1] FSSP: {len(fssp)} records, sources={fssp_sources}, type={fssp_type}")
    for f_rec in fssp[:5]:
        log(f"    - {str(f_rec.get('subject', f_rec.get('description', '?')))[:60]} | Source: {f_rec.get('source', '?')}")
    result['stages']['fssp'] = {'count': len(fssp), 'sources': list(fssp_sources), 'data_type': fssp_type}

    # Stage 1: Bankruptcy
    bankruptcy = _ensure_list(data.get('bankruptcy_records'))
    log(f"  [Stage 1] Bankruptcy: {len(bankruptcy)} records")
    result['stages']['bankruptcy'] = {'count': len(bankruptcy)}

    # Stage 2: Sanctions
    sanctions = _ensure_list(data.get('sanctions_results'))
    sanctions_found = [s for s in sanctions if s.get('found')]
    sanctions_checked = [s for s in sanctions if s.get('checked')]
    log(f"  [Stage 2] Sanctions: {len(sanctions_checked)} checked, {len(sanctions_found)} hits")
    for s in sanctions:
        status = "FOUND" if s.get('found') else "Clear" if s.get('checked') else "Not checked"
        log(f"    - {s.get('source_name', '?')}: {status}")
    result['stages']['sanctions'] = {
        'checked': len(sanctions_checked),
        'found': len(sanctions_found),
        'sources': [s.get('source_name') for s in sanctions]
    }

    # Stage 3: Social Media
    social = _ensure_list(data.get('social_media_profiles'))
    confirmed = _ensure_list(data.get('confirmed_profiles'))
    log(f"  [Stage 3] Social Media: {len(social)} profiles found, {len(confirmed)} confirmed")
    for p in social[:10]:
        platform = p.get('platform', '?')
        display = p.get('display_name', '')
        if not display:
            display = (str(p.get('first_name', '')) + ' ' + str(p.get('last_name', ''))).strip()
        url = p.get('url', p.get('profile_url', ''))
        city = p.get('city', '')
        log(f"    - [{platform}] {display} | {city} | {url}")
    platforms = list(set(p.get('platform', '') for p in social))
    result['stages']['social'] = {'count': len(social), 'confirmed': len(confirmed), 'platforms': platforms}

    # Stage 4: Contacts
    contacts = data.get('contact_discoveries', {})
    if isinstance(contacts, str):
        try:
            contacts = json.loads(contacts)
        except:
            contacts = {}
    if isinstance(contacts, dict):
        phones = contacts.get('phones', [])
        emails = contacts.get('emails', [])
    elif isinstance(contacts, list):
        phones = [c for c in contacts if c.get('type') == 'phone']
        emails = [c for c in contacts if c.get('type') == 'email']
    else:
        phones, emails = [], []
    log(f"  [Stage 4] Contacts: {len(phones)} phones, {len(emails)} emails")
    for p in phones[:5]:
        if isinstance(p, dict):
            log(f"    Phone: {p.get('value', p.get('phone', '?'))} | Source: {p.get('source', '?')} | Conf: {p.get('confidence', '?')}")
        else:
            log(f"    Phone: {p}")
    for e in emails[:5]:
        if isinstance(e, dict):
            log(f"    Email: {e.get('value', e.get('email', '?'))} | Source: {e.get('source', '?')} | Conf: {e.get('confidence', '?')}")
        else:
            log(f"    Email: {e}")
    result['stages']['contacts'] = {'phones': len(phones), 'emails': len(emails)}

    # Stage 5: Deep Social
    face_matches = _ensure_list(data.get('face_matches'))
    username_accounts = _ensure_list(data.get('username_accounts'))
    social_graph = data.get('social_graph_data', {})
    if isinstance(social_graph, str):
        try:
            social_graph = json.loads(social_graph)
        except:
            social_graph = {}
    graph_nodes = len(social_graph.get('nodes', [])) if isinstance(social_graph, dict) else 0
    log(f"  [Stage 5] Face matches: {len(face_matches)} | Username accounts: {len(username_accounts)} | Graph nodes: {graph_nodes}")
    for fm in face_matches[:3]:
        log(f"    Face: {fm.get('url', fm.get('profile_url', '?'))} | Score: {fm.get('score', fm.get('similarity', '?'))}")
    for ua in username_accounts[:5]:
        log(f"    Username: {ua.get('site', '?')} | {ua.get('url', '?')}")
    result['stages']['deep_social'] = {
        'face_matches': len(face_matches),
        'username_accounts': len(username_accounts),
        'graph_nodes': graph_nodes
    }

    # Stage 6: Behavioral
    geo = data.get('geo_analysis', {})
    if isinstance(geo, str):
        try:
            geo = json.loads(geo)
        except:
            geo = {}
    text_data = data.get('text_analysis', {})
    if isinstance(text_data, str):
        try:
            text_data = json.loads(text_data)
        except:
            text_data = {}
    timeline = _ensure_list(data.get('activity_timeline'))
    geo_locs = len(geo.get('locations', [])) if isinstance(geo, dict) else 0
    log(f"  [Stage 6] Geo locations: {geo_locs} | Text analysis: {bool(text_data)} | Timeline entries: {len(timeline)}")
    result['stages']['behavioral'] = {
        'geo_locations': geo_locs,
        'has_text_analysis': bool(text_data),
        'timeline_entries': len(timeline)
    }

    # Stage 7: Risk
    risk_level = risk.get('risk_level', '')
    risk_display = risk.get('risk_level_display', '')
    risk_score = risk.get('risk_score_numeric', '')
    red_flags = _ensure_list(risk.get('red_flags'))
    risk_breakdown = risk.get('risk_breakdown', {})
    if isinstance(risk_breakdown, str):
        try:
            risk_breakdown = json.loads(risk_breakdown)
        except:
            risk_breakdown = {}

    log(f"\n  [Stage 7] Risk Level: {risk_level} ({risk_display}) | Score: {risk_score}")
    log(f"  [Stage 7] Red Flags: {len(red_flags)}")
    for rf in red_flags:
        sev = rf.get('severity', '?')
        desc = rf.get('description', rf.get('detail', '?'))
        cat = rf.get('category', '')
        log(f"    [{sev}] {cat}: {desc}")

    if isinstance(risk_breakdown, dict) and risk_breakdown:
        log(f"  [Stage 7] Risk Breakdown:")
        for cat, score in risk_breakdown.items():
            if isinstance(score, (int, float)):
                bar = '#' * int(score * 10) if score <= 1 else '#' * min(int(score), 10)
                log(f"    {cat}: {score} {bar}")

    result['risk_level'] = risk_level
    result['risk_display'] = risk_display
    result['risk_score'] = risk_score
    result['red_flags'] = red_flags

    # Stage 8: Report
    log(f"  [Stage 8] Report generated: {meta.get('report_generated', '?')}")

    # Summary
    log(f"\n  --- DATA SOURCE SUMMARY ---")
    for stage_name, stage_data in result['stages'].items():
        dtype = stage_data.get('data_type', 'N/A')
        icon = {'REAL': '[REAL]', 'DEMO': '[DEMO]', 'EMPTY': '[EMPTY]'}.get(dtype, '[?]')
        log(f"  {icon} {stage_name}")


def _ensure_list(val):
    """Ensure value is a list."""
    if val is None:
        return []
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except:
            return []
    if isinstance(val, list):
        return val
    return []


def classify_data(records, sources):
    """Classify data as REAL, DEMO, or EMPTY."""
    if not records:
        return 'EMPTY'
    sources_str = str(sources).lower()
    if 'demo' in sources_str or 'mock' in sources_str or 'fake' in sources_str:
        return 'DEMO'
    return 'REAL'


def print_final_report(all_results):
    """Print comprehensive report across all 5 candidates."""

    log(f"\n\n{'='*70}")
    log(f"FINAL REPORT -- {len(all_results)} REAL CANDIDATES")
    log(f"{'='*70}")

    completed = [r for r in all_results if r['status'] in ('COMPLETE', 'COMPLETE_NO_JSON')]
    failed = [r for r in all_results if r['status'] not in ('COMPLETE', 'COMPLETE_NO_JSON', 'REJECTED')]
    rejected = [r for r in all_results if r['status'] == 'REJECTED']

    log(f"\nResults:")
    log(f"  Completed: {len(completed)}")
    log(f"  Failed: {len(failed)}")
    log(f"  Rejected: {len(rejected)}")

    durations = [r['duration'] for r in all_results if r['duration'] > 0]
    avg_duration = sum(durations) / len(durations) if durations else 0
    log(f"  Avg duration: {avg_duration:.1f}s")

    # Data source analysis
    log(f"\n{'='*70}")
    log(f"DATA SOURCE ANALYSIS -- What's REAL vs DEMO")
    log(f"{'='*70}")

    stage_names = ['business', 'courts', 'fssp', 'sanctions', 'social', 'contacts', 'deep_social', 'behavioral']

    for stage in stage_names:
        real_count = 0
        demo_count = 0
        empty_count = 0
        has_data = 0

        for r in completed:
            stage_data = r['stages'].get(stage, {})
            dtype = stage_data.get('data_type', '')
            if dtype == 'REAL':
                real_count += 1
            elif dtype == 'DEMO':
                demo_count += 1
            elif dtype == 'EMPTY':
                empty_count += 1

            count = stage_data.get('count', 0)
            if count and count > 0:
                has_data += 1

        total = real_count + demo_count + empty_count
        data_info = f" (data in {has_data}/{len(completed)})" if has_data else ""
        if total > 0:
            log(f"  {stage:15s}: REAL={real_count} | DEMO={demo_count} | EMPTY={empty_count}{data_info}")
        else:
            log(f"  {stage:15s}: (no classification){data_info}")

    # Red flag summary
    log(f"\n{'='*70}")
    log(f"RED FLAGS FOUND")
    log(f"{'='*70}")

    for r in completed:
        name = r['candidate']
        risk_lvl = r.get('risk_level', '?')
        risk_display = r.get('risk_display', '')
        score = r.get('risk_score', '')
        flags = r.get('red_flags', [])
        log(f"\n  {name}: {risk_lvl} ({risk_display}) score={score}, {len(flags)} flags")
        for rf in flags:
            sev = rf.get('severity', '?')
            desc = rf.get('description', rf.get('detail', '?'))
            cat = rf.get('category', '')
            log(f"    [{sev}] {cat}: {desc}")

    # Per-candidate summary table
    log(f"\n{'='*70}")
    log(f"PER-CANDIDATE SUMMARY")
    log(f"{'='*70}")

    for r in all_results:
        name = r['candidate']
        status = r['status']
        duration = r['duration']
        risk_lvl = r.get('risk_level', 'N/A')
        biz = r['stages'].get('business', {}).get('count', 0)
        courts_n = r['stages'].get('courts', {}).get('count', 0)
        social_n = r['stages'].get('social', {}).get('count', 0)
        phones = r['stages'].get('contacts', {}).get('phones', 0)
        emails = r['stages'].get('contacts', {}).get('emails', 0)
        usernames = r['stages'].get('deep_social', {}).get('username_accounts', 0)
        flags = len(r.get('red_flags', []))

        log(f"\n  {name}")
        log(f"    Status: {status} | Duration: {duration:.0f}s | Risk: {risk_lvl}")
        log(f"    Business: {biz} | Courts: {courts_n} | Social: {social_n}")
        log(f"    Phones: {phones} | Emails: {emails} | Username accounts: {usernames}")
        log(f"    Red flags: {flags}")
        if r.get('error'):
            log(f"    Error: {r['error']}")


def main():
    log(f"{'='*70}")
    log(f"IBP REAL CANDIDATE TEST -- {datetime.now().isoformat()}")
    log(f"Target: {BASE_URL}")
    log(f"Candidates: {len(CANDIDATES)}")
    log(f"{'='*70}")

    session = requests.Session()
    if not login(session):
        log("FATAL: Cannot login. Aborting.")
        return

    all_results = []

    for i, candidate in enumerate(CANDIDATES, 1):
        result = run_candidate(session, candidate, i)
        all_results.append(result)

        if i < len(CANDIDATES):
            log(f"\n  Waiting 10s before next candidate...")
            time.sleep(10)

    print_final_report(all_results)

    # Save full results to JSON
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'real_candidate_results.json')
    save_results = []
    for r in all_results:
        save_r = dict(r)
        save_results.append(save_r)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'base_url': BASE_URL,
            'candidates_tested': len(CANDIDATES),
            'results': save_results,
        }, f, ensure_ascii=False, indent=2, default=str)

    log(f"\n\nFull results saved to: {output_path}")


if __name__ == '__main__':
    main()
