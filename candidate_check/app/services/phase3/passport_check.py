"""
Passport Validity Check — MVD Database
=======================================
Checks a Russian passport (series + number) against the MVD
invalid passport database (ГУВМ МВД России).

Public service: https://xn--b1ab2a0a.xn--b1aew.xn--p1ai/info-service.htm?sid=2000
(сервисы.гувм.мвд.рф)
"""

import logging
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def normalize_passport(raw: str) -> tuple:
    """
    Normalize passport input to (series, number).

    Accepts: '0312 107459', '0312107459', '03 12 107459'
    Returns: ('0312', '107459') or (None, None) on invalid input.
    """
    digits = re.sub(r'\D', '', raw.strip())
    if len(digits) != 10:
        return None, None
    return digits[:4], digits[4:]


def check_passport_mvd(series: str, number: str) -> dict:
    """
    Check passport against MVD invalid passport database.

    Returns:
        {
            'valid': bool | None,     # True=valid, False=invalid, None=unknown
            'status': str,            # Human-readable status
            'checked': bool,          # Whether the check actually ran
            'error': str | None,      # Error message if any
        }
    """
    if not series or not number:
        return {
            'valid': None,
            'checked': False,
            'error': 'Серия или номер паспорта не указаны',
        }

    # Validate format
    if not re.match(r'^\d{4}$', series) or not re.match(r'^\d{6}$', number):
        return {
            'valid': None,
            'checked': False,
            'error': f'Неверный формат: серия={series}, номер={number}',
        }

    try:
        url = 'https://xn--b1ab2a0a.xn--b1aew.xn--p1ai/info-service.htm'
        params = {'sid': '2000'}
        data = {
            'sid': '2000',
            'form_name': 'form',
            'DOC_SERIE': series,
            'DOC_NUMBER': number,
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://xn--b1ab2a0a.xn--b1aew.xn--p1ai/info-service.htm?sid=2000',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

        r = requests.post(url, params=params, data=data,
                          headers=headers, timeout=15, verify=True)

        if r.status_code != 200:
            return {
                'valid': None,
                'checked': False,
                'error': f'HTTP {r.status_code}',
            }

        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text().lower()

        # Check for known response patterns
        if 'не значится' in text or 'среди недействительных не значится' in text:
            return {
                'valid': True,
                'status': 'Действителен (не числится среди недействительных)',
                'checked': True,
                'error': None,
            }
        elif 'недействителен' in text or 'числится' in text:
            return {
                'valid': False,
                'status': 'Недействителен (числится в базе МВД)',
                'checked': True,
                'error': None,
            }
        else:
            # Service returned a response but we couldn't parse it
            logger.warning(f"MVD passport check: unexpected response for {series} {number}")
            return {
                'valid': None,
                'status': 'Статус не определён',
                'checked': True,
                'error': 'Не удалось распознать ответ сервиса',
            }

    except requests.Timeout:
        return {
            'valid': None,
            'checked': False,
            'error': 'Таймаут подключения к сервису МВД',
        }
    except requests.ConnectionError:
        return {
            'valid': None,
            'checked': False,
            'error': 'Не удалось подключиться к сервису МВД',
        }
    except Exception as e:
        logger.warning(f"MVD passport check error: {e}")
        return {
            'valid': None,
            'checked': False,
            'error': str(e),
        }
