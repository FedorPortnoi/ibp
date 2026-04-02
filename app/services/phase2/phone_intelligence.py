"""
Phone Intelligence Service
===========================
Searches free sources for phone number intelligence.
No paid APIs required.
"""
import asyncio
import logging
import os
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

TIMEOUT = 10


def _normalize_phone(phone: str) -> Optional[str]:
    """Normalize Russian phone to +7XXXXXXXXXX."""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 11 and digits[0] in ('7', '8'):
        return '+7' + digits[1:]
    elif len(digits) == 10:
        return '+7' + digits
    return None


def _search_hudsonrock(phone_digits: str) -> dict:
    """Check phone in HudsonRock Cavalier free API."""
    try:
        r = requests.get(
            'https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-phone',
            params={'phone': phone_digits},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            stealers = data.get('stealers', [])
            if stealers:
                emails = list(set(
                    s.get('email', '') for s in stealers if s.get('email')
                ))[:5]
                return {
                    'found': True,
                    'stealer_count': len(stealers),
                    'emails': emails,
                    'source': 'HudsonRock',
                }
        return {'found': False}
    except Exception as e:
        logger.debug(f"HudsonRock phone search: {e}")
        return {'error': str(e)}


def _search_leakcheck(phone: str) -> dict:
    """Check phone in LeakCheck public API."""
    try:
        r = requests.get(
            f'https://leakcheck.io/api/public?check={requests.utils.quote(phone)}',
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            return {
                'found': data.get('found', 0) > 0,
                'count': data.get('found', 0),
                'sources': data.get('sources', []),
            }
        return {'found': False}
    except Exception as e:
        logger.debug(f"LeakCheck phone search: {e}")
        return {'error': str(e)}


def run_phone_intelligence(phone: str) -> dict:
    """
    Run all free phone intelligence sources.
    Synchronous — suitable for pipeline integration.
    """
    phone_norm = _normalize_phone(phone)
    if not phone_norm:
        return {'phone': phone, 'error': 'Invalid phone', 'sources': {}}

    phone_digits = phone_norm.replace('+', '')
    results = {
        'phone': phone,
        'phone_normalized': phone_norm,
        'sources': {},
    }

    # HudsonRock
    results['sources']['hudsonrock'] = _search_hudsonrock(phone_digits)

    # LeakCheck
    results['sources']['leakcheck'] = _search_leakcheck(phone_norm)

    # Aggregate
    emails = []
    breach_count = 0
    for src, data in results['sources'].items():
        if not isinstance(data, dict) or not data.get('found'):
            continue
        if 'emails' in data:
            emails.extend(data['emails'])
        if 'stealer_count' in data:
            breach_count += data['stealer_count']

    results['summary'] = {
        'emails_found': list(set(emails))[:5],
        'breach_count': breach_count,
        'total_sources_with_data': sum(
            1 for d in results['sources'].values()
            if isinstance(d, dict) and d.get('found')
        ),
    }
    return results
