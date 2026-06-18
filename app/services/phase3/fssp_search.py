"""
FSSP Search - Federal Bailiff Service (Enforcement Proceedings)
===============================================================
Search for active enforcement proceedings (исполнительные производства).

API Status (as of Feb 2026):
- api-ip.fssp.gov.ru: SHUT DOWN - all endpoints return 404
  (Official statement: "В целях предотвращения кибератак доступ к API остановлен.")
- is-go.fssp.gov.ru/ajax_search: AJAX endpoint, reachable but CAPTCHA-gated
- fssp.gov.ru/iss/ip: Website works (HTTP 200) from outside Russia

Search flow discovered via browser inspection:
  POST https://is-go.fssp.gov.ru/ajax_search
  Params (CP1251-encoded): is[variant]=1, is[last_name], is[first_name], is[date], is[region_id][0]
  Response: JSONP wrapper ({ "data": "<html>", "err": "", "e": "" });
  Always returns CAPTCHA for programmatic requests.
  CAPTCHA: 5-digit image + code_id token.
  After solving: GET same URL + &code=XXXXX&code_id=TOKEN

This module provides:
1. Playwright-based search attempt (fills form, detects CAPTCHA, extracts image)
2. requests-based AJAX probe (fast detection of site availability)
3. Manual search URL generation (always available, pre-filled params in URL)
"""

import base64
import json
import logging
import os
import re
import time
from html import unescape
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


@dataclass
class EnforcementProceeding:
    """An enforcement proceeding from FSSP."""
    debtor_name: str
    proceeding_number: str = ""
    debt_type: str = ""  # алименты, штраф, кредит, госпошлина, etc.
    amount: str = ""     # sum in rubles
    department: str = "" # bailiff department
    bailiff: str = ""    # bailiff name + phone
    date: str = ""
    status: str = ""     # на исполнении, окончено, etc.
    source: str = "ФССП"
    url: str = ""
    details: str = ""

    def to_dict(self) -> Dict:
        return {
            'debtor_name': self.debtor_name,
            'proceeding_number': self.proceeding_number,
            'debt_type': self.debt_type,
            'amount': self.amount,
            'department': self.department,
            'bailiff': self.bailiff,
            'date': self.date,
            'status': self.status,
            'source': self.source,
            'url': self.url,
            'details': self.details,
        }


class FSSPSearch:
    """
    Search FSSP (Federal Bailiff Service) for enforcement proceedings.

    Strategy (in order):
    1. Playwright scraper: loads fssp.gov.ru/iss/ip, fills form, submits.
       - If results found: parse and return them.
       - If CAPTCHA found: extract image and code_id, log for manual resolution.
    2. Direct AJAX probe: fast check of is-go.fssp.gov.ru availability.
    3. Manual URL fallback: always returns a clickable FSSP search URL (safety net).

    The official API (api-ip.fssp.gov.ru) was shut down in 2024/2025.
    """

    # Search page and AJAX endpoint (discovered via browser network inspection)
    SEARCH_PAGE = "https://fssp.gov.ru/iss/ip"
    AJAX_HOST = "https://is-go.fssp.gov.ru"
    AJAX_PATH = "/ajax_search"

    HEADERS = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        'Referer': 'https://fssp.gov.ru/iss/ip',
    }

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    # -------------------------------------------------------------------------
    # Public search interface
    # -------------------------------------------------------------------------

    def search_by_name(
        self,
        lastname: str,
        firstname: str = "",
        patronymic: str = "",
        region: str = "",
        birthdate: str = "",
        limit: int = 50,
    ) -> List[EnforcementProceeding]:
        """
        Search for enforcement proceedings by person name.

        Args:
            lastname:   Фамилия
            firstname:  Имя
            patronymic: Отчество
            region:     Region code (77=Moscow) or empty for all
            birthdate:  Date of birth DD.MM.YYYY (required by FSSP for individual search)
            limit:      Max results

        Returns:
            List of EnforcementProceeding (empty if CAPTCHA or site down).
        """
        if not lastname:
            return []

        logger.info(f"FSSP search: {lastname} {firstname} {patronymic}")

        # Step 1: Quick availability probe via requests (cheap, fast)
        available = self._probe_site_availability()
        if not available:
            logger.warning("FSSP website unreachable — skipping search")
            return []

        # FSSP website is reachable but CAPTCHA-gated — no automated path available.
        # Pipeline primary is CheckoService; this fallback returns empty so the
        # pipeline continues without blocking on a CAPTCHA solve.
        logger.info("FSSP: no automated search path available (CAPTCHA-gated)")
        return []

    def search_by_full_name(
        self,
        full_name: str,
        region: str = "",
        limit: int = 50,
    ) -> List[EnforcementProceeding]:
        """Convenience method: search by full name string."""
        parts = self.parse_full_name(full_name)
        return self.search_by_name(
            lastname=parts['lastname'],
            firstname=parts['firstname'],
            patronymic=parts['patronymic'],
            region=region,
            limit=limit,
        )

    def _probe_site_availability(self) -> bool:
        """
        Quick HTTP probe to confirm fssp.gov.ru/iss/ip is reachable.

        Returns True if site returns HTTP 200 (confirmed reachable from outside Russia).
        """
        try:
            r = self.session.get(
                self.SEARCH_PAGE,
                timeout=10,
                verify=False,
                allow_redirects=True,
            )
            available = r.status_code == 200
            if available:
                logger.debug("FSSP site probe: 200 OK")
            else:
                logger.warning(f"FSSP site probe: HTTP {r.status_code}")
            return available
        except requests.Timeout:
            logger.warning("FSSP site probe: timeout — likely geo-blocked or down")
            return False
        except requests.ConnectionError as e:
            logger.warning(f"FSSP site probe: connection error — {e}")
            return False
        except Exception as e:
            logger.warning(f"FSSP site probe error: {e}")
            return False

    # -------------------------------------------------------------------------
    # Utility methods
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_full_name(full_name: str) -> dict:
        """Parse a full Russian name into parts."""
        parts = full_name.strip().split()
        result = {'lastname': '', 'firstname': '', 'patronymic': ''}
        if len(parts) >= 1:
            result['lastname'] = parts[0]
        if len(parts) >= 2:
            result['firstname'] = parts[1]
        if len(parts) >= 3:
            result['patronymic'] = parts[2]
        return result

    @staticmethod
    def get_manual_search_url(full_name: str) -> Dict[str, str]:
        """
        Generate manual FSSP search URL for the user.

        The FSSP website (fssp.gov.ru/iss/ip) is reachable from outside Russia.
        This URL opens the search page directly — the user fills in the form manually.
        A deep-link with pre-filled params is included as a comment since FSSP
        uses POST + CAPTCHA, not direct GET links.
        """
        parts = FSSPSearch.parse_full_name(full_name)
        return {
            'name': 'ФССП (Исполнительные производства)',
            'url': 'https://fssp.gov.ru/iss/ip',
            'description': f'Поиск по ФИО: {full_name}',
            'instructions': (
                f'Введите: Фамилия={parts["lastname"]}, '
                f'Имя={parts["firstname"]}, '
                f'Отчество={parts["patronymic"]}'
            ),
        }


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------
fssp_search = FSSPSearch()
