"""
Direct Pipeline Runner
======================
Runs the candidate pipeline in-process (no HTTP server needed).
"""
import os, sys, json, time, io, uuid
from datetime import date

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

from app import create_app, db
from app.models.candidate_check import CandidateCheck
from app.services.candidate.pipeline import run_candidate_pipeline, candidate_tasks, CandidateTaskStatus

app = create_app()

with app.app_context():
    # Create check record
    check_id = uuid.uuid4().hex
    full_name = 'Иван Петров'
    check = CandidateCheck(
        id=check_id,
        full_name=full_name,
        date_of_birth=date(1990, 6, 15),
        region='Москва',
        check_mode='quick',
        status='pending',
    )
    db.session.add(check)
    db.session.commit()
    print(f'Created check: {check_id}')

    # Create task status
    task_id = uuid.uuid4().hex
    task_status = CandidateTaskStatus(task_id, check_id, full_name)
    candidate_tasks[task_id] = task_status

    # Run pipeline in background thread
    import threading
    t = threading.Thread(
        target=run_candidate_pipeline,
        args=(app, task_id, check_id),
        daemon=True
    )
    t.start()
    print('Pipeline started in background thread')
    print()

    # Poll progress via CandidateTaskStatus attributes
    print('=== Pipeline Progress ===')
    last_pct = -1
    for i in range(900):  # max 15 min
        time.sleep(1)
        ts = candidate_tasks.get(task_id)
        if not ts:
            if i % 10 == 0:
                print(f'  [{i}s] Task not found')
            continue

        pct = ts.percent_complete
        stage = ts.current_step
        d = ts.to_dict()
        status = d['status']

        if pct != last_pct:
            print(f'  [{pct:3d}%] {stage} (status={status})')
            last_pct = pct

        if status in ('complete', 'error', 'cancelled'):
            print(f'  Final: {status}')
            if ts.error:
                print(f'  Error: {ts.error}')
            break
    else:
        print('  TIMEOUT after 15 minutes')

    # Give DB a moment to flush
    time.sleep(2)

    # Read results
    print()
    print('=== Reading Results ===')
    db.session.expire_all()
    check = db.session.get(CandidateCheck, check_id)

    def safe_json(val):
        if val is None:
            return {}
        if isinstance(val, str):
            try:
                return json.loads(val)
            except:
                return {}
        return val

    print(f'Check ID: {check.id}')
    print(f'Full name: {check.full_name}')
    print(f'Status: {check.status}')
    print(f'Mode: {check.check_mode}')
    print(f'Duration: {check.check_duration_seconds}s')
    print(f'Sources checked: {check.sources_checked}')
    print(f'Sources with results: {check.sources_with_results}')
    print()

    # Stage 1
    print('--- Stage 1: Government Registries ---')
    business = safe_json(check.business_records)
    courts = safe_json(check.court_records)
    fssp = safe_json(check.fssp_records)
    bankruptcy = safe_json(check.bankruptcy_records)
    biz_list = business if isinstance(business, list) else business.get('records', business.get('results', []))
    court_list = courts if isinstance(courts, list) else courts.get('records', courts.get('results', courts.get('cases', [])))
    fssp_list = fssp if isinstance(fssp, list) else fssp.get('records', fssp.get('results', []))
    bank_list = bankruptcy if isinstance(bankruptcy, list) else bankruptcy.get('records', bankruptcy.get('results', []))
    print(f'  EGRUL/business: {len(biz_list) if isinstance(biz_list, list) else "?"} records')
    print(f'  Court records: {len(court_list) if isinstance(court_list, list) else "?"} records')
    print(f'  FSSP records: {len(fssp_list) if isinstance(fssp_list, list) else "?"} records')
    print(f'  Bankruptcy: {len(bank_list) if isinstance(bank_list, list) else "?"} records')

    # Stage 2
    print('--- Stage 2: Security Checks ---')
    sanctions = safe_json(check.sanctions_results)
    if isinstance(sanctions, list):
        print(f'  Sanctions: {len(sanctions)} results')
    elif isinstance(sanctions, dict):
        total = sum(len(v) for v in sanctions.values() if isinstance(v, list))
        print(f'  Sanctions: {total} total ({", ".join(f"{k}={len(v)}" for k,v in sanctions.items() if isinstance(v, list))})')
    red_flags = safe_json(check.red_flags)
    rf_list = red_flags if isinstance(red_flags, list) else []
    print(f'  Red flags: {len(rf_list)} (count field: {check.red_flag_count})')
    for rf in rf_list[:5]:
        if isinstance(rf, dict):
            print(f'    - [{rf.get("severity", "?")}] {rf.get("description", rf.get("text", "?"))[:100]}')

    # Stage 3
    print('--- Stage 3: Social Media ---')
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
    print(f'  VK profiles: {len(vk)}')
    for p in vk[:8]:
        pid = p.get('id', p.get('vk_id', '?'))
        fn = p.get('first_name', '')
        ln = p.get('last_name', '')
        city = p.get('city', '')
        if isinstance(city, dict):
            city = city.get('title', '')
        bdate = p.get('bdate', '')
        print(f'    - id{pid}: {fn} {ln}, city={city}, bdate={bdate}')
    print(f'  Telegram: {len(tg)}')
    for t in tg[:8]:
        un = t.get('username', 'no-username')
        fn = t.get('first_name', '')
        ln = t.get('last_name', '')
        print(f'    - @{un} ({fn} {ln})')
    print(f'  OK.ru: {len(ok)}')

    # Stage 4
    print('--- Stage 4: Contact Discovery ---')
    contacts = safe_json(check.contact_discoveries)
    if isinstance(contacts, dict):
        phones = contacts.get('phones', [])
        emails = contacts.get('emails', [])
    elif isinstance(contacts, list):
        phones = [c for c in contacts if c.get('type') == 'phone']
        emails = [c for c in contacts if c.get('type') == 'email']
    else:
        phones = emails = []
    print(f'  Phones found: {len(phones)}')
    for ph in phones[:20]:
        src = ph.get('sources', [ph.get('source', '?')])
        conf = ph.get('confidence_score', ph.get('confidence', '?'))
        val = ph.get('phone', ph.get('value', '?'))
        print(f'    - {val} (conf={conf}, src={src})')
    print(f'  Emails found: {len(emails)}')
    for em in emails[:20]:
        src = em.get('sources', [em.get('source', '?')])
        conf = em.get('confidence_score', em.get('confidence', '?'))
        val = em.get('email', em.get('value', '?'))
        print(f'    - {val} (conf={conf}, src={src})')

    # Stage 5
    print('--- Stage 5: Deep Social Analysis ---')
    face = safe_json(check.face_matches)
    face_results = face if isinstance(face, list) else face.get('results', face.get('matches', []))
    print(f'  Face matches: {len(face_results)}')
    for fm in (face_results[:5] if isinstance(face_results, list) else []):
        print(f'    - score={fm.get("score", "?")}, db={fm.get("database", fm.get("source", "?"))}')

    graph = safe_json(check.social_graph_data)
    nodes = graph.get('nodes', []) if isinstance(graph, dict) else []
    edges = graph.get('edges', graph.get('links', [])) if isinstance(graph, dict) else []
    communities = graph.get('communities', []) if isinstance(graph, dict) else []
    print(f'  Social graph: {len(nodes)} nodes, {len(edges)} edges, {len(communities)} communities')

    usernames = safe_json(check.username_accounts)
    if isinstance(usernames, list):
        # Flat list format: each item has 'source' field ('snoop', 'maigret', 'sherlock', 'yaseeker')
        snoop_r = [a for a in usernames if a.get('source') == 'snoop']
        maigret_r = [a for a in usernames if a.get('source') == 'maigret']
        sherlock_r = [a for a in usernames if a.get('source') == 'sherlock']
    elif isinstance(usernames, dict):
        snoop_data = usernames.get('snoop', {})
        maigret_data = usernames.get('maigret', {})
        sherlock_data = usernames.get('sherlock', {})
        snoop_r = snoop_data.get('results', snoop_data.get('found', [])) if isinstance(snoop_data, dict) else []
        maigret_r = maigret_data.get('results', maigret_data.get('found', [])) if isinstance(maigret_data, dict) else []
        sherlock_r = sherlock_data.get('results', sherlock_data.get('found', [])) if isinstance(sherlock_data, dict) else []
    else:
        snoop_r = maigret_r = sherlock_r = []
    print(f'  Snoop: {len(snoop_r)} results')
    print(f'  Maigret: {len(maigret_r)} results')
    print(f'  Sherlock: {len(sherlock_r)} results')

    # Stage 6
    print('--- Stage 6: Behavioral ---')
    text_an = safe_json(check.text_analysis)
    wall_posts = text_an.get('posts_analyzed', 0) if isinstance(text_an, dict) else 0
    print(f'  Wall posts analyzed: {wall_posts}')
    if isinstance(text_an, dict):
        keywords = text_an.get('keywords', [])
        if keywords:
            print(f'  Keywords: {keywords[:10]}')
        sentiment = text_an.get('sentiment', {})
        if sentiment:
            print(f'  Sentiment: {json.dumps(sentiment, ensure_ascii=False)[:200]}')

    geo = safe_json(check.geo_analysis)
    geo_locs = geo.get('locations', []) if isinstance(geo, dict) else []
    print(f'  Geo locations: {len(geo_locs)}')
    for gl in geo_locs[:5]:
        if isinstance(gl, dict):
            print(f'    - {gl.get("city", gl.get("name", gl))}')
        else:
            print(f'    - {gl}')

    timeline = safe_json(check.activity_timeline)
    timeline_events = timeline.get('events', []) if isinstance(timeline, dict) else (timeline if isinstance(timeline, list) else [])
    print(f'  Timeline events: {len(timeline_events)}')

    # Stage 7
    print('--- Stage 7: Risk Scoring ---')
    print(f'  Risk level: {check.risk_level}')
    print(f'  Risk score: {check.risk_score_numeric}')
    breakdown = safe_json(check.risk_breakdown)
    if isinstance(breakdown, dict):
        for cat, val in breakdown.items():
            if isinstance(val, dict):
                print(f'    {cat}: {val.get("level", "?")} ({val.get("score", "?")})')
            else:
                print(f'    {cat}: {val}')

    # Summary
    print()
    print('=' * 50)
    print('=== SUMMARY ===')
    print('=' * 50)
    print(f'VK profiles found:     {len(vk)}')
    print(f'Telegram accounts:     {len(tg)}')
    print(f'OK.ru profiles:        {len(ok)}')
    print(f'Phones discovered:     {len(phones)}')
    print(f'Emails discovered:     {len(emails)}')
    print(f'Face matches:          {len(face_results) if isinstance(face_results, list) else "?"}')
    print(f'Social graph nodes:    {len(nodes)}')
    print(f'Social graph edges:    {len(edges)}')
    print(f'Wall posts scanned:    {wall_posts}')
    print(f'Snoop accounts:        {len(snoop_r)}')
    print(f'Maigret accounts:      {len(maigret_r)}')
    print(f'Sherlock accounts:     {len(sherlock_r)}')
    print(f'Geo locations:         {len(geo_locs)}')
    print(f'Risk level:            {check.risk_level}')
    print(f'Risk score:            {check.risk_score_numeric}')
