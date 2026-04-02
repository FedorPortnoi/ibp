"""
INN Breach Search — Check INN in breach databases.
"""
import logging
import requests

logger = logging.getLogger(__name__)

TIMEOUT = 10


def search_inn_in_breaches(inn: str) -> dict:
    """
    Search INN number in breach databases.
    INN sometimes appears as username or in leaked government portal data.
    """
    if not inn or len(inn) not in (10, 12):
        return {'found': False, 'reason': 'Invalid INN', 'sources': {}}

    results = {'inn': inn, 'sources': {}, 'found': False}

    # LeakCheck public API
    try:
        r = requests.get(
            f'https://leakcheck.io/api/public?check={inn}',
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            results['sources']['leakcheck'] = {
                'found': data.get('found', 0) > 0,
                'count': data.get('found', 0),
                'sources': data.get('sources', []),
            }
    except Exception as e:
        results['sources']['leakcheck'] = {'error': str(e)}

    # HudsonRock — search by INN as email pattern
    try:
        r = requests.get(
            'https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-email',
            params={'email': f'{inn}@nalog.ru'},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get('stealers'):
                results['sources']['hudsonrock'] = {
                    'found': True,
                    'stealers': len(data['stealers']),
                }
            else:
                results['sources']['hudsonrock'] = {'found': False}
    except Exception as e:
        results['sources']['hudsonrock'] = {'error': str(e)}

    results['found'] = any(
        s.get('found') for s in results['sources'].values()
        if isinstance(s, dict)
    )
    return results
