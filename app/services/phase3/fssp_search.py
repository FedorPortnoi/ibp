"""
FSSP Search - Federal Bailiff Service (Enforcement Proceedings)
===============================================================
Search for active enforcement proceedings (исполнительные производства).

API Status (as of Feb 2026):
- api-ip.fssp.gov.ru: SSL errors, unreliable
- is.fssp.gov.ru: Returns 503
- fssp.gov.ru/iss/ip: Website works but requires JS rendering

This module provides:
1. API-based search (when FSSP_API_TOKEN is configured and API is operational)
2. Manual search URL generation (always available)
"""

import logging
import os
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import quote
import requests

logger = logging.getLogger(__name__)


@dataclass
class EnforcementProceeding:
    """An enforcement proceeding from FSSP."""
    debtor_name: str
    proceeding_number: str = ""
    debt_type: str = ""  # алименты, штраф, кредит, госпошлина, etc.
    amount: str = ""  # sum in rubles
    department: str = ""  # bailiff department
    bailiff: str = ""  # bailiff name + phone
    date: str = ""
    status: str = ""  # на исполнении, окончено, etc.
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

    The FSSP API (api-ip.fssp.gov.ru) requires registration and a token.
    As of Feb 2026, the API has SSL issues and may not be operational.

    This module gracefully handles API unavailability by:
    1. Attempting API search if token is configured
    2. Falling back to manual search URL generation
    """

    API_BASE = "https://api-ip.fssp.gov.ru/api/v1.0"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    # Region codes for major Russian cities
    REGIONS = {
        'москва': '77',
        'московская область': '50',
        'санкт-петербург': '78',
        'ленинградская область': '47',
    }

    def __init__(self, api_token: str = None, timeout: int = 30):
        self.api_token = api_token or os.environ.get('FSSP_API_TOKEN', '')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._api_available = None  # Unknown until tested

    def search_by_name(
        self,
        lastname: str,
        firstname: str = "",
        patronymic: str = "",
        region: str = "",
        birthdate: str = "",
        limit: int = 50
    ) -> List[EnforcementProceeding]:
        """
        Search for enforcement proceedings by person name.

        Args:
            lastname: Фамилия
            firstname: Имя
            patronymic: Отчество
            region: Region code (77=Moscow) or empty for all
            birthdate: Date of birth (DD.MM.YYYY) for precise matching
            limit: Max results

        Returns:
            List of EnforcementProceeding objects
        """
        if not lastname:
            return []

        logger.info(f"FSSP search: {lastname} {firstname} {patronymic}")

        # Try API if token is available
        if self.api_token and self._api_available is not False:
            try:
                results = self._search_api(lastname, firstname, patronymic, region, birthdate, limit)
                if results is not None:
                    self._api_available = True
                    return results
            except Exception as e:
                logger.warning(f"FSSP API error: {e}")
                self._api_available = False

        # API not available
        if not self.api_token:
            logger.info("FSSP API token not configured — skipping API search")
        else:
            logger.warning("FSSP API unavailable — generating manual search links only")

        return []

    def _search_api(
        self,
        lastname: str,
        firstname: str,
        patronymic: str,
        region: str,
        birthdate: str,
        limit: int
    ) -> Optional[List[EnforcementProceeding]]:
        """
        Search FSSP API (async: submit → poll for results).

        Returns None if API is unreachable.
        """
        # Step 1: Submit search
        params = {
            'token': self.api_token,
            'region': region or '',
            'lastname': lastname,
            'firstname': firstname,
        }
        if patronymic:
            params['secondname'] = patronymic
        if birthdate:
            params['birthdate'] = birthdate

        try:
            resp = self.session.get(
                f"{self.API_BASE}/search/physical",
                params=params,
                timeout=self.timeout
            )
        except requests.ConnectionError:
            logger.warning("FSSP API connection failed")
            return None
        except requests.Timeout:
            logger.warning("FSSP API timeout")
            return None

        if resp.status_code != 200:
            logger.warning(f"FSSP API returned {resp.status_code}")
            return None

        try:
            data = resp.json()
        except Exception:
            logger.warning("FSSP API returned non-JSON response")
            return None

        if data.get('code') != 0:
            error_msg = data.get('message', 'Unknown error')
            logger.warning(f"FSSP API error: {error_msg}")
            return None

        task_id = data.get('task', '')
        if not task_id:
            logger.warning("FSSP API returned no task ID")
            return None

        # Step 2: Poll for results
        time.sleep(3)

        for attempt in range(5):
            try:
                resp2 = self.session.get(
                    f"{self.API_BASE}/result",
                    params={'token': self.api_token, 'task': task_id},
                    timeout=self.timeout
                )

                if resp2.status_code != 200:
                    time.sleep(2)
                    continue

                data2 = resp2.json()

                if data2.get('code') == 0:
                    results = []
                    for item in (data2.get('result', []) or [])[:limit]:
                        proc = self._parse_api_result(item)
                        if proc:
                            results.append(proc)
                    return results
                elif data2.get('code') == 1:
                    # Task not ready yet
                    time.sleep(3)
                    continue
                else:
                    break

            except Exception as e:
                logger.warning(f"FSSP poll attempt {attempt+1} error: {e}")
                time.sleep(2)

        return []

    def _parse_api_result(self, item: dict) -> Optional[EnforcementProceeding]:
        """Parse a single FSSP API result item."""
        try:
            return EnforcementProceeding(
                debtor_name=item.get('name', ''),
                proceeding_number=item.get('ip_number', '') or item.get('number', ''),
                debt_type=item.get('subject', '') or item.get('exe_production', ''),
                amount=str(item.get('debt_rest', '')) or str(item.get('sum', '')),
                department=item.get('department', '') or item.get('dep', ''),
                bailiff=item.get('bailiff', ''),
                date=item.get('ip_end', '') or item.get('date', ''),
                status='На исполнении',
                source='ФССП',
                details=item.get('details', ''),
            )
        except Exception as e:
            logger.debug(f"Parse FSSP item error: {e}")
            return None

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

    def search_by_full_name(self, full_name: str, region: str = "", limit: int = 50) -> List[EnforcementProceeding]:
        """Convenience method: search by full name string."""
        parts = self.parse_full_name(full_name)
        return self.search_by_name(
            lastname=parts['lastname'],
            firstname=parts['firstname'],
            patronymic=parts['patronymic'],
            region=region,
            limit=limit
        )

    @staticmethod
    def get_manual_search_url(full_name: str) -> Dict[str, str]:
        """Generate manual FSSP search URL for the user."""
        parts = FSSPSearch.parse_full_name(full_name)
        return {
            'name': 'ФССП (Исполнительные производства)',
            'url': 'https://fssp.gov.ru/iss/ip',
            'description': f'Поиск по ФИО: {full_name}',
            'instructions': f'Введите: Фамилия={parts["lastname"]}, Имя={parts["firstname"]}, Отчество={parts["patronymic"]}'
        }


# Singleton instance
fssp_search = FSSPSearch()
