"""
E2E Court Investigation Test
=============================
1. Search sudact.ru for real court cases
2. Pick a subject with active court history
3. Run the full 8-stage pipeline on them
4. Report everything found — real data, no demos
"""
import os, sys, json, time, io, uuid, logging, threading
from datetime import date, datetime

# UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Configure logging — show service-level info
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
# Quiet noisy libs
for name in ('urllib3', 'httpx', 'httpcore', 'asyncio', 'PIL', 'matplotlib'):
    logging.getLogger(name).setLevel(logging.WARNING)

SEPARATOR = '=' * 70
SUB_SEP = '-' * 50

def safe_json(val):
    if val is None:
        return {}
    if isinstance(val, str):
        try:
            return json.loads(val)
        except:
            return {}
    return val

def extract_list(data, *keys):
    """Extract a list from data by trying multiple dict keys, or return data if already a list."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in keys:
            if k in data and isinstance(data[k], list):
                return data[k]
    return []


# =====================================================================
# STEP 1: FIND REAL COURT CASE SUBJECTS
# =====================================================================
print(SEPARATOR)
print('STEP 1: SEARCHING SUDACT.RU FOR REAL COURT CASES')
print(SEPARATOR)
print()

from app import create_app, db
app = create_app()

with app.app_context():
    from app.services.phase3.court_search import CourtRecordSearch
    from app.services.phase3.casebook_service import CasebookService
    from app.services.phase3.business_registry import BusinessRegistrySearch

    # Search sudact.ru for cases mentioning ООО or ИП (business-related disputes)
    court_searcher = CourtRecordSearch(timeout=30)

    # Strategy: search for a common Russian business-related name to find court-active people
    # We'll search for several names and pick the one with the most results
    search_queries = [
        'Кузнецов Алексей Владимирович',
        'Сидорова Елена Николаевна',
        'Козлов Дмитрий Сергеевич',
    ]

    best_name = None
    best_cases = []

    for query in search_queries:
        print(f'Searching sudact.ru for: {query}')
        try:
            cases = court_searcher.search_by_name(query, limit=20)
            print(f'  Found {len(cases)} court cases')
            for c in cases[:3]:
                print(f'    - {c.case_number} | {c.court_name} | {c.case_type} | {c.date}')

            if len(cases) > len(best_cases):
                best_cases = cases
                best_name = query
        except Exception as e:
            print(f'  Error: {e}')
        print()

    # Also try casebook.ru for arbitration cases
    casebook = CasebookService(timeout=25)
    casebook_cases = []
    for query in search_queries[:2]:
        print(f'Searching casebook.ru for: {query}')
        try:
            cb_cases = casebook.search_person(query)
            print(f'  Found {len(cb_cases)} arbitration cases')
            for c in cb_cases[:3]:
                print(f'    - {c.case_number} | {c.court_name} | {c.date}')
            if cb_cases:
                casebook_cases.extend(cb_cases)
                if not best_name or not best_cases:
                    best_name = query
        except Exception as e:
            print(f'  Error: {e}')
        print()

    # If sudact didn't return results (JS rendering issue), fall back to a known court-active name
    if not best_cases and not casebook_cases:
        print('No cases found via automated search. Using fallback subject.')
        best_name = 'Кузнецов Алексей Владимирович'
        print(f'Subject: {best_name}')
        print()

    SUBJECT_NAME = best_name
    print(SEPARATOR)
    print(f'SELECTED SUBJECT: {SUBJECT_NAME}')
    print(f'Court cases from sudact.ru: {len(best_cases)}')
    print(f'Arbitration cases from casebook.ru: {len(casebook_cases)}')
    print(SEPARATOR)
    print()

    # Show all found court cases in detail
    if best_cases:
        print('=== SUDACT.RU COURT CASES ===')
        for i, c in enumerate(best_cases, 1):
            print(f'  [{i}] Case: {c.case_number}')
            print(f'      Court: {c.court_name}')
            print(f'      Type:  {c.case_type}')
            print(f'      Date:  {c.date}')
            print(f'      Role:  {c.role}')
            print(f'      URL:   {c.url}')
            print()

    if casebook_cases:
        print('=== CASEBOOK.RU ARBITRATION CASES ===')
        for i, c in enumerate(casebook_cases, 1):
            print(f'  [{i}] Case: {c.case_number}')
            print(f'      Court: {c.court_name}')
            print(f'      Type:  {c.case_type}')
            print(f'      Date:  {c.date}')
            print()

    # =====================================================================
    # STEP 2: RUN FULL 8-STAGE PIPELINE
    # =====================================================================
    print()
    print(SEPARATOR)
    print(f'STEP 2: RUNNING FULL 8-STAGE PIPELINE ON: {SUBJECT_NAME}')
    print(SEPARATOR)
    print()

    from app.models.candidate_check import CandidateCheck
    from app.services.candidate.pipeline import run_candidate_pipeline, candidate_tasks, CandidateTaskStatus

    check_id = uuid.uuid4().hex
    check = CandidateCheck(
        id=check_id,
        full_name=SUBJECT_NAME,
        date_of_birth=date(1985, 1, 1),  # Approximate — pipeline uses name as primary key
        region='',  # Let it search nationwide
        check_mode='quick',
        status='pending',
    )
    db.session.add(check)
    db.session.commit()
    print(f'Created CandidateCheck: {check_id}')

    task_id = uuid.uuid4().hex
    task_status = CandidateTaskStatus(task_id, check_id, SUBJECT_NAME)
    candidate_tasks[task_id] = task_status
    print(f'Created task: {task_id}')
    print()

    # Start pipeline in background thread
    t = threading.Thread(
        target=run_candidate_pipeline,
        args=(app, task_id, check_id),
        daemon=True
    )
    start_time = time.time()
    t.start()
    print('Pipeline started...')
    print()

    # Poll progress
    last_pct = -1
    last_step = ''
    for i in range(1200):  # max 20 min
        time.sleep(1)
        ts = candidate_tasks.get(task_id)
        if not ts:
            continue

        pct = ts.percent_complete
        step = ts.current_step
        d = ts.to_dict()
        status = d['status']

        if pct != last_pct or step != last_step:
            elapsed = time.time() - start_time
            print(f'  [{pct:3d}%] [{elapsed:6.1f}s] {step}')
            last_pct = pct
            last_step = step

        if status in ('complete', 'error', 'cancelled'):
            elapsed = time.time() - start_time
            print(f'  Pipeline finished: {status} in {elapsed:.1f}s')
            if ts.error:
                print(f'  ERROR: {ts.error}')
            break
    else:
        print('  TIMEOUT after 20 minutes')

    time.sleep(2)

    # =====================================================================
    # STEP 3: DETAILED RESULTS REPORT
    # =====================================================================
    print()
    print(SEPARATOR)
    print('STEP 3: INVESTIGATION RESULTS')
    print(SEPARATOR)
    print()

    db.session.expire_all()
    check = db.session.get(CandidateCheck, check_id)

    print(f'Subject:          {check.full_name}')
    print(f'Status:           {check.status}')
    print(f'Mode:             {check.check_mode}')
    print(f'Duration:         {check.check_duration_seconds}s')
    print(f'Sources checked:  {check.sources_checked}')
    print(f'Sources w/results: {check.sources_with_results}')
    print()

    # ── STAGE 1: Government Registries ──
    print(SEPARATOR)
    print('STAGE 1: GOVERNMENT REGISTRIES')
    print(SEPARATOR)

    business = safe_json(check.business_records)
    biz_list = extract_list(business, 'records', 'results')
    print(f'\nEGRUL Business Records: {len(biz_list)}')
    for i, b in enumerate(biz_list, 1):
        print(f'  [{i}] {b.get("company_name", b.get("name", "?"))}')
        print(f'      INN: {b.get("inn", "?")} | OGRN: {b.get("ogrn", "?")}')
        print(f'      Role: {b.get("role", "?")} | Status: {b.get("status", "?")}')
        print(f'      Registered: {b.get("registration_date", "?")}')
        print(f'      Address: {b.get("address", "?")}')
        print(f'      Source: {b.get("source", "?")}')
        print()

    courts = safe_json(check.court_records)
    court_list = extract_list(courts, 'records', 'results', 'cases')
    print(f'Court Records: {len(court_list)}')
    for i, c in enumerate(court_list, 1):
        print(f'  [{i}] Case: {c.get("case_number", "?")}')
        print(f'      Court: {c.get("court_name", "?")}')
        print(f'      Type: {c.get("case_type", "?")} | Role: {c.get("role", "?")}')
        print(f'      Date: {c.get("date", "?")}')
        print(f'      Result: {c.get("result", "?")}')
        print(f'      Source: {c.get("source", "?")}')
        print()

    fssp = safe_json(check.fssp_records)
    fssp_list = extract_list(fssp, 'records', 'results')
    print(f'FSSP Enforcement: {len(fssp_list)}')
    total_debt = 0
    for i, f in enumerate(fssp_list, 1):
        amt = f.get('amount', 0) or 0
        total_debt += float(amt) if amt else 0
        print(f'  [{i}] {f.get("proceedings_number", "?")}')
        print(f'      Subject: {f.get("subject", "?")}')
        print(f'      Amount: {amt} RUB')
        print(f'      Active: {f.get("is_active", "?")}')
        print(f'      Department: {f.get("department", "?")}')
        print(f'      Source: {f.get("source", "?")}')
        print()
    if total_debt:
        print(f'  TOTAL DEBT: {total_debt:,.0f} RUB')

    bankruptcy = safe_json(check.bankruptcy_records)
    bank_list = extract_list(bankruptcy, 'records', 'results')
    print(f'\nBankruptcy Records: {len(bank_list)}')
    for b in bank_list:
        print(f'  - {json.dumps(b, ensure_ascii=False)[:200]}')

    print(f'\n{SUB_SEP}')
    print(f'Stage 1 Summary: {len(biz_list)} businesses, {len(court_list)} court cases, '
          f'{len(fssp_list)} FSSP proceedings, {len(bank_list)} bankruptcies')
    if total_debt:
        print(f'  Total enforcement debt: {total_debt:,.0f} RUB')

    # ── STAGE 2: Security Checks ──
    print(f'\n{SEPARATOR}')
    print('STAGE 2: SECURITY CHECKS')
    print(SEPARATOR)

    sanctions = safe_json(check.sanctions_results)
    if isinstance(sanctions, list):
        print(f'Sanctions results: {len(sanctions)}')
        for s in sanctions:
            src = s.get('source_name', s.get('source', '?'))
            found = s.get('found', False)
            print(f'  - {src}: {"FOUND" if found else "clean"}')
            if found:
                matches = s.get('matches', s.get('results', []))
                for m in (matches[:5] if isinstance(matches, list) else []):
                    print(f'      Match: {json.dumps(m, ensure_ascii=False)[:150]}')
    elif isinstance(sanctions, dict):
        for src, results in sanctions.items():
            if isinstance(results, list):
                print(f'  {src}: {len(results)} results')
                for r in results[:3]:
                    print(f'    - {json.dumps(r, ensure_ascii=False)[:150]}')
            elif isinstance(results, bool):
                print(f'  {src}: {"FOUND" if results else "clean"}')
            else:
                print(f'  {src}: {results}')

    red_flags = safe_json(check.red_flags)
    rf_list = extract_list(red_flags, 'flags', 'results')
    print(f'\nRed flags: {len(rf_list)} (count: {check.red_flag_count})')
    for rf in rf_list[:10]:
        if isinstance(rf, dict):
            print(f'  - [{rf.get("severity", "?")}] {rf.get("description", rf.get("text", "?"))[:120]}')

    # ── STAGE 3: Social Media Discovery ──
    print(f'\n{SEPARATOR}')
    print('STAGE 3: SOCIAL MEDIA DISCOVERY')
    print(SEPARATOR)

    social = safe_json(check.social_media_profiles)
    if isinstance(social, dict):
        vk = social.get('vk', [])
        tg = social.get('telegram', [])
        ok = social.get('ok', [])
    elif isinstance(social, list):
        vk = [p for p in social if p.get('platform') == 'vk']
        tg = [p for p in social if p.get('platform') == 'telegram']
        ok = [p for p in social if p.get('platform') == 'ok']
    else:
        vk = tg = ok = []

    print(f'\nVK Profiles: {len(vk)}')
    for i, p in enumerate(vk, 1):
        pid = p.get('id', p.get('vk_id', '?'))
        fn = p.get('first_name', '')
        ln = p.get('last_name', '')
        city = p.get('city', '')
        if isinstance(city, dict):
            city = city.get('title', '')
        bdate = p.get('bdate', '')
        verified = p.get('verified', '')
        photo = p.get('photo_max_orig', p.get('photo_200', ''))
        print(f'  [{i}] id{pid}: {fn} {ln}')
        print(f'      City: {city} | DOB: {bdate} | Verified: {verified}')
        if photo:
            print(f'      Photo: {photo[:80]}...')
        print()

    print(f'Telegram Profiles: {len(tg)}')
    for i, t_prof in enumerate(tg, 1):
        un = t_prof.get('username', 'no-username')
        fn = t_prof.get('first_name', '')
        ln = t_prof.get('last_name', '')
        tid = t_prof.get('id', t_prof.get('user_id', '?'))
        print(f'  [{i}] @{un} ({fn} {ln}) [id: {tid}]')

    print(f'\nOK.ru Profiles: {len(ok)}')
    for i, o in enumerate(ok, 1):
        print(f'  [{i}] {o.get("name", o.get("display_name", "?"))} — {o.get("url", "?")}')

    # ── STAGE 4: Contact Discovery ──
    print(f'\n{SEPARATOR}')
    print('STAGE 4: CONTACT DISCOVERY')
    print(SEPARATOR)

    contacts = safe_json(check.contact_discoveries)
    if isinstance(contacts, dict):
        phones = contacts.get('phones', [])
        emails = contacts.get('emails', [])
    elif isinstance(contacts, list):
        phones = [c for c in contacts if c.get('type') == 'phone']
        emails = [c for c in contacts if c.get('type') == 'email']
    else:
        phones = emails = []

    print(f'\nPhones Discovered: {len(phones)}')
    for i, ph in enumerate(phones, 1):
        val = ph.get('phone', ph.get('value', '?'))
        conf = ph.get('confidence_score', ph.get('confidence', '?'))
        src = ph.get('sources', [ph.get('source', '?')])
        label = ph.get('confidence', '')
        print(f'  [{i}] {val}')
        print(f'      Confidence: {conf} ({label}) | Sources: {src}')

    print(f'\nEmails Discovered: {len(emails)}')
    for i, em in enumerate(emails, 1):
        val = em.get('email', em.get('value', '?'))
        conf = em.get('confidence_score', em.get('confidence', '?'))
        src = em.get('sources', [em.get('source', '?')])
        verified = em.get('verified', '')
        print(f'  [{i}] {val}')
        print(f'      Confidence: {conf} | Verified: {verified} | Sources: {src}')

    # ── STAGE 5: Deep Social Analysis ──
    print(f'\n{SEPARATOR}')
    print('STAGE 5: DEEP SOCIAL ANALYSIS')
    print(SEPARATOR)

    face = safe_json(check.face_matches)
    face_results = extract_list(face, 'results', 'matches')
    print(f'\nFace Matches (Search4Faces): {len(face_results)}')
    for i, fm in enumerate(face_results[:10], 1):
        score = fm.get('score', fm.get('similarity', '?'))
        db_name = fm.get('database', fm.get('source', '?'))
        profile = fm.get('profile_url', fm.get('url', ''))
        name = fm.get('name', fm.get('full_name', ''))
        print(f'  [{i}] Score: {score} | DB: {db_name} | Name: {name}')
        if profile:
            print(f'      Profile: {profile}')

    graph = safe_json(check.social_graph_data)
    nodes = graph.get('nodes', []) if isinstance(graph, dict) else []
    edges = graph.get('edges', graph.get('links', [])) if isinstance(graph, dict) else []
    communities = graph.get('communities', []) if isinstance(graph, dict) else []
    print(f'\nSocial Graph: {len(nodes)} nodes, {len(edges)} edges, {len(communities)} communities')
    if communities:
        for i, comm in enumerate(communities[:5], 1):
            if isinstance(comm, dict):
                members = comm.get('members', [])
                label = comm.get('label', f'Community {i}')
                print(f'  Community "{label}": {len(members)} members')
            elif isinstance(comm, list):
                print(f'  Community {i}: {len(comm)} members')

    # Top nodes by centrality
    if nodes:
        sorted_nodes = sorted(
            [n for n in nodes if isinstance(n, dict)],
            key=lambda x: x.get('centrality', x.get('centrality_score', 0)),
            reverse=True
        )
        if sorted_nodes:
            print(f'\n  Top nodes by centrality:')
            for n in sorted_nodes[:8]:
                print(f'    - {n.get("label", n.get("name", "?"))} '
                      f'(centrality={n.get("centrality", n.get("centrality_score", "?"))})')

    usernames = safe_json(check.username_accounts)
    if isinstance(usernames, list):
        snoop_r = [a for a in usernames if a.get('source') == 'snoop']
        maigret_r = [a for a in usernames if a.get('source') == 'maigret']
        sherlock_r = [a for a in usernames if a.get('source') == 'sherlock']
        yaseeker_r = [a for a in usernames if a.get('source') == 'yaseeker']
    elif isinstance(usernames, dict):
        snoop_data = usernames.get('snoop', {})
        maigret_data = usernames.get('maigret', {})
        sherlock_data = usernames.get('sherlock', {})
        yaseeker_data = usernames.get('yaseeker', {})
        snoop_r = extract_list(snoop_data, 'results', 'found') if isinstance(snoop_data, dict) else []
        maigret_r = extract_list(maigret_data, 'results', 'found') if isinstance(maigret_data, dict) else []
        sherlock_r = extract_list(sherlock_data, 'results', 'found') if isinstance(sherlock_data, dict) else []
        yaseeker_r = extract_list(yaseeker_data, 'results', 'found') if isinstance(yaseeker_data, dict) else []
    else:
        snoop_r = maigret_r = sherlock_r = yaseeker_r = []

    print(f'\nUsername Search Results:')
    print(f'  Snoop (5,372 sites):    {len(snoop_r)} accounts found')
    print(f'  Maigret (3,000+ sites): {len(maigret_r)} accounts found')
    print(f'  Sherlock (400+ sites):  {len(sherlock_r)} accounts found')
    print(f'  YaSeeker (Yandex):      {len(yaseeker_r)} accounts found')

    # Show some accounts
    all_username_results = snoop_r + maigret_r + sherlock_r + yaseeker_r
    if all_username_results:
        print(f'\n  Sample accounts:')
        for a in all_username_results[:15]:
            site = a.get('site', a.get('platform', a.get('name', '?')))
            url = a.get('url', a.get('link', ''))
            src = a.get('source', '?')
            print(f'    - [{src}] {site}: {url}')

    # ── STAGE 6: Behavioral Intelligence ──
    print(f'\n{SEPARATOR}')
    print('STAGE 6: BEHAVIORAL INTELLIGENCE')
    print(SEPARATOR)

    text_an = safe_json(check.text_analysis)
    if isinstance(text_an, dict):
        wall_posts = text_an.get('posts_analyzed', 0)
        print(f'\nWall Posts Analyzed: {wall_posts}')

        keywords = text_an.get('keywords', [])
        if keywords:
            print(f'Keywords: {", ".join(str(k) for k in keywords[:15])}')

        sentiment = text_an.get('sentiment', {})
        if sentiment:
            print(f'Sentiment: {json.dumps(sentiment, ensure_ascii=False)}')

        topics = text_an.get('topics', [])
        if topics:
            print(f'Topics: {", ".join(str(t) for t in topics[:10])}')

        language = text_an.get('language_stats', text_an.get('languages', {}))
        if language:
            print(f'Language: {json.dumps(language, ensure_ascii=False)[:200]}')
    else:
        print('  No text analysis data')

    geo = safe_json(check.geo_analysis)
    geo_locs = geo.get('locations', []) if isinstance(geo, dict) else []
    print(f'\nGeo Locations Extracted: {len(geo_locs)}')
    for gl in geo_locs[:10]:
        if isinstance(gl, dict):
            city = gl.get('city', gl.get('name', '?'))
            count = gl.get('count', gl.get('mentions', ''))
            lat = gl.get('lat', '')
            lon = gl.get('lon', gl.get('lng', ''))
            print(f'  - {city} (mentions: {count}, coords: {lat},{lon})')
        else:
            print(f'  - {gl}')

    timeline = safe_json(check.activity_timeline)
    if isinstance(timeline, dict):
        events = timeline.get('events', [])
    elif isinstance(timeline, list):
        events = timeline
    else:
        events = []
    print(f'\nActivity Timeline Events: {len(events)}')
    for ev in events[:10]:
        if isinstance(ev, dict):
            ts_val = ev.get('timestamp', ev.get('date', ev.get('time', '?')))
            desc = ev.get('description', ev.get('text', ev.get('event', '?')))
            print(f'  - [{ts_val}] {str(desc)[:100]}')

    # ── STAGE 7: Risk Scoring ──
    print(f'\n{SEPARATOR}')
    print('STAGE 7: RISK SCORING')
    print(SEPARATOR)

    print(f'\nRisk Level:  {check.risk_level}')
    print(f'Risk Score:  {check.risk_score_numeric}')

    breakdown = safe_json(check.risk_breakdown)
    if isinstance(breakdown, dict):
        print(f'\nRisk Breakdown by Category:')
        for cat, val in breakdown.items():
            if isinstance(val, dict):
                level = val.get('level', '?')
                score = val.get('score', '?')
                factors = val.get('factors', val.get('details', []))
                print(f'  {cat}: {level} (score: {score})')
                if factors and isinstance(factors, list):
                    for factor in factors[:3]:
                        if isinstance(factor, dict):
                            print(f'    - {factor.get("text", factor.get("description", json.dumps(factor, ensure_ascii=False)[:100]))}')
                        else:
                            print(f'    - {str(factor)[:100]}')
            else:
                print(f'  {cat}: {val}')

    # ── STAGE 8: Report ──
    print(f'\n{SEPARATOR}')
    print('STAGE 8: REPORT DATA')
    print(SEPARATOR)

    # Export JSON
    results_file = os.path.join(PROJECT_ROOT, 'scripts', f'investigation_{check_id[:12]}.json')
    export_data = {
        'subject': check.full_name,
        'check_id': check.id,
        'status': check.status,
        'mode': check.check_mode,
        'duration_seconds': check.check_duration_seconds,
        'sources_checked': check.sources_checked,
        'sources_with_results': check.sources_with_results,
        'stages': {
            '1_business_records': biz_list,
            '1_court_records': court_list,
            '1_fssp_records': fssp_list,
            '1_bankruptcy': bank_list,
            '2_sanctions': safe_json(check.sanctions_results),
            '2_red_flags': rf_list,
            '3_social_media': safe_json(check.social_media_profiles),
            '4_contacts': safe_json(check.contact_discoveries),
            '5_face_matches': face_results,
            '5_social_graph': {'nodes': len(nodes), 'edges': len(edges), 'communities': len(communities)},
            '5_username_accounts': {
                'snoop': len(snoop_r),
                'maigret': len(maigret_r),
                'sherlock': len(sherlock_r),
                'yaseeker': len(yaseeker_r),
            },
            '6_text_analysis': safe_json(check.text_analysis),
            '6_geo': safe_json(check.geo_analysis),
            '6_timeline': safe_json(check.activity_timeline),
            '7_risk': {
                'level': check.risk_level,
                'score': check.risk_score_numeric,
                'breakdown': safe_json(check.risk_breakdown),
            },
        },
    }

    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
    print(f'\nJSON export saved: {results_file}')

    # ═══════════════════════════════════════════
    # FINAL SUMMARY
    # ═══════════════════════════════════════════
    print()
    print(SEPARATOR)
    print('INVESTIGATION SUMMARY')
    print(SEPARATOR)
    print(f'Subject:              {SUBJECT_NAME}')
    print(f'Pipeline status:      {check.status}')
    print(f'Duration:             {check.check_duration_seconds}s')
    print(f'Sources checked:      {check.sources_checked}')
    print(f'Sources with results: {check.sources_with_results}')
    print()
    print(f'Business records:     {len(biz_list)}')
    print(f'Court cases:          {len(court_list)}')
    print(f'FSSP proceedings:     {len(fssp_list)}')
    print(f'Bankruptcy records:   {len(bank_list)}')
    if total_debt:
        print(f'Total FSSP debt:      {total_debt:,.0f} RUB')
    print()
    print(f'Sanctions matches:    {len(sanctions) if isinstance(sanctions, list) else "see above"}')
    print(f'Red flags:            {len(rf_list)}')
    print()
    print(f'VK profiles:          {len(vk)}')
    print(f'Telegram accounts:    {len(tg)}')
    print(f'OK.ru profiles:       {len(ok)}')
    print()
    print(f'Phones discovered:    {len(phones)}')
    print(f'Emails discovered:    {len(emails)}')
    print()
    print(f'Face matches:         {len(face_results)}')
    print(f'Social graph nodes:   {len(nodes)}')
    print(f'Social graph edges:   {len(edges)}')
    print(f'Communities:          {len(communities)}')
    print()
    print(f'Snoop accounts:       {len(snoop_r)}')
    print(f'Maigret accounts:     {len(maigret_r)}')
    print(f'Sherlock accounts:    {len(sherlock_r)}')
    print(f'YaSeeker results:     {len(yaseeker_r)}')
    print()
    print(f'Wall posts analyzed:  {text_an.get("posts_analyzed", 0) if isinstance(text_an, dict) else 0}')
    print(f'Geo locations:        {len(geo_locs)}')
    print(f'Timeline events:      {len(events)}')
    print()
    print(f'RISK LEVEL:           {check.risk_level}')
    print(f'RISK SCORE:           {check.risk_score_numeric}')
    print()
    print(f'JSON export:          {results_file}')
    print(SEPARATOR)
    print('E2E COURT INVESTIGATION TEST COMPLETE')
    print(SEPARATOR)
