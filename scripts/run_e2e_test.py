"""
E2E Pipeline Test Script
========================
Runs a full candidate check pipeline and reports results.
"""

import os
import json
import time
import sys
import re

# Disable CSRF for test
os.environ['WTF_CSRF_ENABLED'] = 'False'

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app import create_app, db
from app.models.candidate_check import CandidateCheck
from app.services.candidate.pipeline import candidate_tasks

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False

with app.test_client() as c:
    # Authenticate first
    ibp_password = os.environ.get('IBP_PASSWORD', '')
    if ibp_password:
        login_resp = c.post('/login', data={
            'password': ibp_password
        }, follow_redirects=True)
        print(f'Login status: {login_resp.status_code}')
    else:
        print('No IBP_PASSWORD set, skipping auth')

    # Start candidate check
    resp = c.post('/candidate/start', json={
        'full_name': 'Иван Петров',
        'date_of_birth': '1990-06-15',
        'city': 'Москва',
        'mode': 'quick'
    })
    print(f'Start status: {resp.status_code}')

    # Follow redirect or get JSON
    task_id = None
    if resp.status_code == 302:
        location = resp.headers.get('Location', '')
        print(f'Redirect to: {location}')
        m = re.search(r'/progress/([a-f0-9-]+)', location)
        if not m:
            m = re.search(r'/progress/(\d+)', location)
        task_id = m.group(1) if m else None
        print(f'Task ID: {task_id}')
    elif resp.status_code == 200:
        data = resp.get_json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        task_id = data.get('task_id')
    else:
        print(resp.get_data(as_text=True)[:500])
        sys.exit(1)

    if not task_id:
        print('ERROR: no task_id found')
        sys.exit(1)

    # Poll progress directly from in-memory task status
    print()
    print('=== Pipeline Progress ===')
    last_pct = -1
    stuck_count = 0
    for i in range(600):  # max 10 min
        time.sleep(1)
        task = candidate_tasks.get(task_id)
        if not task:
            print(f'  Task {task_id} not found in memory')
            continue

        pct = getattr(task, 'progress', 0)
        stage = getattr(task, 'stage', '')
        status = getattr(task, 'status', '')

        if pct != last_pct:
            print(f'  [{pct:3d}%] {stage}')
            last_pct = pct
            stuck_count = 0
        else:
            stuck_count += 1

        if status in ('completed', 'failed', 'error'):
            print(f'  Final status: {status}')
            if status != 'completed':
                print(f'  Error: {getattr(task, "error", "")}')
            break

        if stuck_count > 180:
            print('  TIMEOUT: stuck for 3 minutes')
            break

    # Get final check data
    print()
    print('=== Final Results ===')

    # Find check_id
    task = candidate_tasks.get(task_id)
    check_id = None
    if task:
        check_id = getattr(task, 'check_id', None)

    if not check_id:
        with app.app_context():
            latest = CandidateCheck.query.order_by(CandidateCheck.id.desc()).first()
            if latest:
                check_id = latest.id

    if not check_id:
        print('Could not find check_id')
        sys.exit(1)

    with app.app_context():
        check = db.session.get(CandidateCheck, check_id)
        if not check:
            print(f'Check {check_id} not found in DB')
            sys.exit(1)

        print(f'Check ID: {check.id}')
        print(f'Status: {check.status}')
        print(f'Full name: {check.full_name}')
        print()

        # Stage 1: Government
        govt = check.government_data or {}
        print('--- Stage 1: Government Registries ---')
        print(f'  EGRUL records: {len(govt.get("egrul", []))}')
        print(f'  Court records: {len(govt.get("courts", []))}')
        print(f'  FSSP records: {len(govt.get("fssp", []))}')
        print(f'  Bankruptcy records: {len(govt.get("bankruptcy", []))}')

        # Stage 2: Security
        sec = check.security_data or {}
        print('--- Stage 2: Security Checks ---')
        print(f'  Sanctions matches: {len(sec.get("sanctions", []))}')
        print(f'  Wanted matches: {len(sec.get("wanted", []))}')
        print(f'  Extremist matches: {len(sec.get("extremist", []))}')

        # Stage 3: Social media
        social = check.social_profiles or {}
        print('--- Stage 3: Social Media ---')
        vk_profiles = social.get('vk', [])
        tg_profiles = social.get('telegram', [])
        ok_profiles = social.get('ok', [])
        print(f'  VK profiles: {len(vk_profiles)}')
        for p in vk_profiles[:5]:
            pid = p.get('id', '?')
            fn = p.get('first_name', '')
            ln = p.get('last_name', '')
            city = p.get('city', {})
            if isinstance(city, dict):
                city = city.get('title', '')
            print(f'    - id{pid}: {fn} {ln}, city={city}')
        print(f'  Telegram: {len(tg_profiles)}')
        for t in tg_profiles[:5]:
            un = t.get('username', 'no-username')
            fn = t.get('first_name', '')
            ln = t.get('last_name', '')
            print(f'    - @{un} ({fn} {ln})')
        print(f'  OK.ru: {len(ok_profiles)}')
        for o in ok_profiles[:5]:
            print(f'    - {o.get("name", o.get("display_name", "?"))} ({o.get("id", "?")})')

        # Stage 4: Contact discovery
        contacts = check.contact_data or {}
        phones = contacts.get('phones', [])
        emails = contacts.get('emails', [])
        print('--- Stage 4: Contact Discovery ---')
        print(f'  Phones found: {len(phones)}')
        for ph in phones[:15]:
            src = ph.get('sources', [ph.get('source', '?')])
            conf = ph.get('confidence_score', ph.get('confidence', '?'))
            val = ph.get('phone', ph.get('value', '?'))
            print(f'    - {val} (conf={conf}, src={src})')
        print(f'  Emails found: {len(emails)}')
        for em in emails[:15]:
            src = em.get('sources', [em.get('source', '?')])
            conf = em.get('confidence_score', em.get('confidence', '?'))
            val = em.get('email', em.get('value', '?'))
            print(f'    - {val} (conf={conf}, src={src})')

        # Stage 5: Deep social
        deep = check.deep_social_data or {}
        print('--- Stage 5: Deep Social Analysis ---')
        face = deep.get('face_search', {})
        graph = deep.get('social_graph', {})
        snoop_d = deep.get('snoop', {})
        maigret_d = deep.get('maigret', {})
        sherlock_d = deep.get('sherlock', {})
        yaseeker_d = deep.get('yaseeker', {})
        face_results = face.get('results', face.get('matches', []))
        print(f'  Face matches: {len(face_results)}')
        for fm in face_results[:5]:
            print(f'    - score={fm.get("score", "?")}, source={fm.get("source", fm.get("database", "?"))}')
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', [])
        communities = graph.get('communities', [])
        print(f'  Social graph: {len(nodes)} nodes, {len(edges)} edges, {len(communities)} communities')
        snoop_results = snoop_d.get('results', snoop_d.get('found', []))
        print(f'  Snoop results: {len(snoop_results)}')
        maigret_results = maigret_d.get('results', maigret_d.get('found', []))
        print(f'  Maigret results: {len(maigret_results)}')
        sherlock_results = sherlock_d.get('results', sherlock_d.get('found', []))
        print(f'  Sherlock results: {len(sherlock_results)}')
        if yaseeker_d:
            print(f'  YaSeeker: {json.dumps(yaseeker_d, ensure_ascii=False)[:300]}')
        else:
            print(f'  YaSeeker: empty')

        # Stage 6: Behavioral
        behav = check.behavioral_data or {}
        print('--- Stage 6: Behavioral ---')
        wall_analysis = behav.get('wall_analysis', {})
        wall_posts = wall_analysis.get('posts_analyzed', 0)
        geo = behav.get('geo', {})
        timeline = behav.get('timeline', {})
        print(f'  Wall posts analyzed: {wall_posts}')
        keywords = wall_analysis.get('keywords', [])
        if keywords:
            print(f'  Top keywords: {keywords[:10]}')
        geo_locs = geo.get('locations', [])
        print(f'  Geo locations: {len(geo_locs)}')
        for gl in geo_locs[:5]:
            print(f'    - {gl}')
        timeline_events = timeline.get('events', [])
        print(f'  Timeline events: {len(timeline_events)}')

        # Stage 7: Risk
        risk = check.risk_data or {}
        print('--- Stage 7: Risk Scoring ---')
        print(f'  Overall level: {risk.get("overall_level", "?")}')
        print(f'  Overall score: {risk.get("overall_score", "?")}')
        cats = risk.get('categories', {})
        for cat, val in cats.items():
            if isinstance(val, dict):
                print(f'    {cat}: {val.get("level", "?")} ({val.get("score", "?")})')

        # Summary
        print()
        print('=' * 50)
        print('=== SUMMARY ===')
        print('=' * 50)
        print(f'VK profiles found:     {len(vk_profiles)}')
        print(f'Telegram accounts:     {len(tg_profiles)}')
        print(f'OK.ru profiles:        {len(ok_profiles)}')
        print(f'Phones discovered:     {len(phones)}')
        print(f'Emails discovered:     {len(emails)}')
        print(f'Face matches:          {len(face_results)}')
        print(f'Social graph nodes:    {len(nodes)}')
        print(f'Social graph edges:    {len(edges)}')
        print(f'Wall posts scanned:    {wall_posts}')
        print(f'Snoop accounts:        {len(snoop_results)}')
        print(f'Maigret accounts:      {len(maigret_results)}')
        print(f'Sherlock accounts:     {len(sherlock_results)}')
        print(f'Geo locations:         {len(geo_locs)}')
        print(f'Risk level:            {risk.get("overall_level", "?")}')
        print(f'Risk score:            {risk.get("overall_score", "?")}')
