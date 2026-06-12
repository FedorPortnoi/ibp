"""
Address Intelligence — Find connections via registered address.

NOTE: despite the "local" label in the pipeline source list, this is a live
HTTP POST to egrul.nalog.ru (FNS). It is reachable from a Russian IP and may
403/timeout elsewhere. Every result carries a `status` so a network failure is
NOT rendered as "no connections at this address" — a mass-registration address
is a risk signal, and a silent failure there is a false clean.
"""
import logging
import requests

logger = logging.getLogger(__name__)

TIMEOUT = 15


def search_by_address(address: str, candidate_inn: str = '') -> dict:
    """
    Search EGRUL for other persons/companies at the same address.

    Returns a dict with `connections`, `mass_registration`, `found`, and a
    `status`: 'ok' (read the address) / 'empty' (read, nothing linked) /
    'blocked' (non-200 from FNS) / 'error' (network/parse failure) /
    'skipped' (address too short). 'blocked'/'error' must never read as a
    clean "no connections" result.
    """
    if not address or len(address) < 10:
        return {'found': False, 'reason': 'Address too short',
                'connections': [], 'status': 'skipped'}

    results = {
        'address': address,
        'connections': [],
        'mass_registration': False,
        'found': False,
        'status': 'error',
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
            # We successfully read the address. 'ok' if it yielded anything
            # (connections or a mass-registration flag), else a genuine 'empty'.
            results['status'] = (
                'ok' if (results['found'] or results['mass_registration'])
                else 'empty'
            )
        else:
            logger.warning(
                f"Address intelligence: FNS returned HTTP {r.status_code}"
            )
            results['status'] = 'blocked'

    except Exception as e:
        logger.warning(f"Address intelligence failed: {e}")
        results['error'] = str(e)
        results['status'] = 'error'

    return results
