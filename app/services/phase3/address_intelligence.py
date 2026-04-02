"""
Address Intelligence — Find connections via registered address.
"""
import logging
import requests

logger = logging.getLogger(__name__)

TIMEOUT = 15


def search_by_address(address: str, candidate_inn: str = '') -> dict:
    """
    Search EGRUL for other persons/companies at the same address.
    Returns connections found at the address.
    """
    if not address or len(address) < 10:
        return {'found': False, 'reason': 'Address too short', 'connections': []}

    results = {
        'address': address,
        'connections': [],
        'mass_registration': False,
        'found': False,
    }

    try:
        # Search nalog.ru by address
        r = requests.post(
            'https://egrul.nalog.ru/search-result',
            data={'query': address, 'region': ''},
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=TIMEOUT,
        )

        if r.status_code == 200:
            data = r.json()
            rows = data.get('rows', [])

            for row in rows[:20]:
                inn = row.get('i', '')
                if inn == candidate_inn:
                    continue
                results['connections'].append({
                    'name': row.get('n', ''),
                    'inn': inn,
                    'ogrn': row.get('o', ''),
                    'status': row.get('s', ''),
                })

            if len(rows) > 10:
                results['mass_registration'] = True
                results['mass_registration_count'] = len(rows)

            results['found'] = len(results['connections']) > 0

    except Exception as e:
        logger.warning(f"Address intelligence failed: {e}")
        results['error'] = str(e)

    return results
