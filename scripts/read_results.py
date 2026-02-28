"""Read latest candidate check results from DB."""
import os, sys, json, time, io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

from app import create_app, db
from app.models.candidate_check import CandidateCheck

app = create_app()

def safe_json(val):
    """Parse JSON string or return dict/list as-is."""
    if val is None:
        return {}
    if isinstance(val, str):
        try:
            return json.loads(val)
        except:
            return {}
    return val

with app.app_context():
    check = CandidateCheck.query.order_by(CandidateCheck.id.desc()).first()
    if not check:
        print('No checks found')
        sys.exit(1)

    print(f'Check ID: {check.id}')
    print(f'Full name: {check.full_name}')
    print(f'DOB: {check.date_of_birth}')
    print(f'Status: {check.status}')
    print(f'Mode: {check.check_mode}')
    print(f'Duration: {check.check_duration_seconds}s')
    print(f'Sources checked: {check.sources_checked}')
    print(f'Sources with results: {check.sources_with_results}')
    print()

    # Stage 1: Government
    print('--- Stage 1: Government Registries ---')
    business = safe_json(check.business_records)
    courts = safe_json(check.court_records)
    fssp = safe_json(check.fssp_records)
    bankruptcy = safe_json(check.bankruptcy_records)
    if isinstance(business, list):
        print(f'  Business/EGRUL records: {len(business)}')
    else:
        records = business.get('records', business.get('results', []))
        print(f'  Business/EGRUL records: {len(records) if isinstance(records, list) else business}')
    if isinstance(courts, list):
        print(f'  Court records: {len(courts)}')
    else:
        records = courts.get('records', courts.get('results', courts.get('cases', [])))
        print(f'  Court records: {len(records) if isinstance(records, list) else courts}')
    if isinstance(fssp, list):
        print(f'  FSSP records: {len(fssp)}')
    else:
        records = fssp.get('records', fssp.get('results', []))
        print(f'  FSSP records: {len(records) if isinstance(records, list) else fssp}')
    if isinstance(bankruptcy, list):
        print(f'  Bankruptcy records: {len(bankruptcy)}')
    else:
        records = bankruptcy.get('records', bankruptcy.get('results', []))
        print(f'  Bankruptcy records: {len(records) if isinstance(records, list) else bankruptcy}')

    # Stage 2: Security
    print('--- Stage 2: Security Checks ---')
    sanctions = safe_json(check.sanctions_results)
    if isinstance(sanctions, list):
        print(f'  Sanctions results: {len(sanctions)}')
    else:
        print(f'  Sanctions: {json.dumps(sanctions, ensure_ascii=False)[:300]}')

    # Red flags
    red_flags = safe_json(check.red_flags)
    if isinstance(red_flags, list):
        print(f'  Red flags: {len(red_flags)}')
        for rf in red_flags[:5]:
            if isinstance(rf, dict):
                print(f'    - [{rf.get("severity", "?")}] {rf.get("description", rf.get("text", "?"))}')
            else:
                print(f'    - {rf}')
    print(f'  Red flag count: {check.red_flag_count}')

    # Stage 3: Social
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
    for o in ok[:5]:
        print(f'    - {o.get("name", o.get("display_name", "?"))}')

    # Stage 4: Contacts
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

    # Stage 5: Deep social
    print('--- Stage 5: Deep Social Analysis ---')
    face = safe_json(check.face_matches)
    face_results = face if isinstance(face, list) else face.get('results', face.get('matches', []))
    print(f'  Face matches: {len(face_results)}')
    for fm in face_results[:5]:
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
        snoop_r = usernames.get('snoop', {}).get('results', usernames.get('snoop', {}).get('found', []))
        maigret_r = usernames.get('maigret', {}).get('results', usernames.get('maigret', {}).get('found', []))
        sherlock_r = usernames.get('sherlock', {}).get('results', usernames.get('sherlock', {}).get('found', []))
    else:
        snoop_r = maigret_r = sherlock_r = []
    print(f'  Snoop results: {len(snoop_r)}')
    print(f'  Maigret results: {len(maigret_r)}')
    print(f'  Sherlock results: {len(sherlock_r)}')

    # Stage 6: Behavioral
    print('--- Stage 6: Behavioral ---')
    text_an = safe_json(check.text_analysis)
    wall_posts = 0
    if isinstance(text_an, dict):
        wall_posts = text_an.get('posts_analyzed', 0)
        keywords = text_an.get('keywords', [])
        if keywords:
            print(f'  Top keywords: {keywords[:10]}')
        sentiment = text_an.get('sentiment', {})
        if sentiment:
            print(f'  Sentiment: {json.dumps(sentiment, ensure_ascii=False)[:200]}')
    print(f'  Wall posts analyzed: {wall_posts}')

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

    # Stage 7: Risk
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
    print(f'Face matches:          {len(face_results)}')
    print(f'Social graph nodes:    {len(nodes)}')
    print(f'Social graph edges:    {len(edges)}')
    print(f'Wall posts scanned:    {wall_posts}')
    print(f'Snoop accounts:        {len(snoop_r)}')
    print(f'Maigret accounts:      {len(maigret_r)}')
    print(f'Sherlock accounts:     {len(sherlock_r)}')
    print(f'Geo locations:         {len(geo_locs)}')
    print(f'Risk level:            {check.risk_level}')
    print(f'Risk score:            {check.risk_score_numeric}')
