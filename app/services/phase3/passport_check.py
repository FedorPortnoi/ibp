"""
Passport Validity Check — MVD Database
=======================================
Checks a Russian passport (series + number) against the MVD
invalid passport database (ГУВМ МВД России).

STATUS (March 2026):
  - Old service (сервисы.гувм.мвд.рф) is DEAD since July 2023.
  - МВД stopped updating the invalid passport registry on 2023-06-21.
  - Госуслуги (gosuslugi.ru/621102/1) requires authentication — not usable for automation.
  - СМЭВ 3 is the only reliable automated alternative (requires govt registration).

Current approach:
  1. Try the old ГУВМ МВД endpoint (works from Russian IP, may be restored)
  2. Graceful "unavailable" fallback when geo-blocked or service is down
  3. Return clear status so pipeline/dossier can display appropriately
"""

import logging
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Primary: old ГУВМ МВД service (geo-blocked outside Russia, may return)
MVD_PRIMARY_URL = 'https://xn--b1ab2a0a.xn--b1aew.xn--p1ai/info-service.htm'

# Status message for when service is unavailable
MVD_UNAVAILABLE_MSG = (
    'Сервис ГУВМ МВД недоступен (прекращён с июля 2023). '
    'Проверка возможна через Госуслуги вручную: gosuslugi.ru/621102/1'
)


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

    # Try the ГУВМ МВД service (may work from Russian IP)
    result = _try_guvm_mvd(series, number)
    if result is not None:
        return result

    # All methods failed — return graceful unavailable
    logger.info(
        f"MVD passport check: all methods unavailable for {series} ******"
    )
    return {
        'valid': None,
        'status': MVD_UNAVAILABLE_MSG,
        'checked': False,
        'error': MVD_UNAVAILABLE_MSG,
    }


def _try_guvm_mvd(series: str, number: str) -> dict | None:
    """
    Try the old ГУВМ МВД endpoint.
    Returns result dict on success, None if service is unreachable.
    """
    try:
        data = {
            'sid': '2000',
            'form_name': 'form',
            'DOC_SERIE': series,
            'DOC_NUMBER': number,
        }
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/131.0.0.0 Safari/537.36'
            ),
            'Referer': f'{MVD_PRIMARY_URL}?sid=2000',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

        r = requests.post(
            MVD_PRIMARY_URL, params={'sid': '2000'}, data=data,
            headers=headers, timeout=10, verify=True,
        )

        if r.status_code == 404:
            logger.info("MVD passport: HTTP 404 — service endpoint moved or removed")
            return None  # Signal to try next method

        if r.status_code != 200:
            logger.info(f"MVD passport check: HTTP {r.status_code}")
            return None

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
            # Service returned a page but not a result (maybe redirect to Gosuslugi)
            if 'госуслуг' in text or 'gosuslugi' in text or 'esia' in text:
                logger.info("MVD passport: redirected to Gosuslugi (auth required)")
                return {
                    'valid': None,
                    'status': 'Сервис МВД перенаправляет на Госуслуги (требуется авторизация)',
                    'checked': False,
                    'error': 'Автоматическая проверка невозможна — сервис требует авторизацию на Госуслугах',
                }
            # Unrecognized page: we could NOT complete the check. Must report
            # checked=False — otherwise the pipeline maps valid=None to
            # found=False and the dossier shows the passport as "verified
            # valid" when nothing was actually confirmed.
            logger.warning(f"MVD passport: unexpected response for {series} ******")
            return {
                'valid': None,
                'status': 'Статус не определён',
                'checked': False,
                'error': 'Не удалось распознать ответ сервиса',
            }

    except (requests.Timeout, requests.ConnectionError) as e:
        # Expected when geo-blocked or service is down
        logger.info(f"MVD passport: service unreachable ({type(e).__name__})")
        return None
    except Exception as e:
        logger.warning(f"MVD passport check error: {e}")
        return None
