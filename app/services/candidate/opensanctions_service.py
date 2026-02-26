"""
OpenSanctions Service — Global Sanctions Database
===================================================
Queries the OpenSanctions API for sanctions matches.
Replaces geo-blocked Russian sources (Rosfinmonitoring, MVD, extremist list)
with a globally accessible, comprehensive sanctions database.

OpenSanctions covers:
- Russian sanctions (Rosfinmonitoring)
- US OFAC/SDN
- EU sanctions
- UN Security Council
- Interpol
- Many national lists

API docs: https://api.opensanctions.org/

Free tier: unlimited searches, no API key required for basic matching.

Usage:
    from app.services.candidate.opensanctions_service import OpenSanctionsService
    svc = OpenSanctionsService()
    results = svc.check_person("Иванов Иван Иванович")
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class OpenSanctionsMatch:
    """A sanctions match from OpenSanctions API."""
    entity_id: str = ''
    name: str = ''
    score: float = 0.0
    datasets: List[str] = None
    countries: List[str] = None
    birth_date: str = ''
    match_details: str = ''
    url: str = ''
    source_name: str = ''

    def __post_init__(self):
        if self.datasets is None:
            self.datasets = []
        if self.countries is None:
            self.countries = []

    def to_dict(self) -> dict:
        return {
            'entity_id': self.entity_id,
            'name': self.name,
            'score': self.score,
            'datasets': self.datasets,
            'countries': self.countries,
            'birth_date': self.birth_date,
            'match_details': self.match_details,
            'url': self.url,
            'source_name': self.source_name,
        }

    def to_sanctions_dict(self) -> dict:
        """Convert to SanctionsResult-compatible dict for pipeline."""
        datasets_str = ', '.join(self.datasets[:5])
        return {
            'source_name': self.source_name or f'OpenSanctions ({datasets_str})',
            'checked': True,
            'found': True,
            'match_details': self.match_details,
            'url': self.url or f'https://opensanctions.org/entities/{self.entity_id}/',
            'error': None,
        }


# Dataset name → Russian display name mapping
DATASET_NAMES = {
    'ru_fedsfm_terror': 'Росфинмониторинг (терроризм)',
    'ru_fedsfm_wmd': 'Росфинмониторинг (ОМУ)',
    'ru_nsd_isin': 'НРД (санкции)',
    'ru_rupep': 'Российские PEP',
    'ru_acf_bribetakers': 'АКФ — взяточники',
    'ru_myrotvorets': 'Миротворец',
    'interpol_api': 'Интерпол',
    'un_sc_sanctions': 'ООН — Совет Безопасности',
    'us_ofac_sdn': 'US OFAC SDN',
    'us_ofac_cons': 'US OFAC Consolidated',
    'eu_fsf': 'EU Financial Sanctions',
    'gb_hmt_sanctions': 'UK HMT Sanctions',
    'ua_nsdc_sanctions': 'Украина СНБО',
}


class OpenSanctionsService:
    """
    Query OpenSanctions API for sanctions matches.

    The API is free, globally accessible, and doesn't require an API key.
    Rate limits are generous for normal usage.

    Usage:
        svc = OpenSanctionsService()
        matches = svc.check_person("Иванов Иван Иванович")
        for m in matches:
            print(m.to_dict())
    """

    API_BASE = 'https://api.opensanctions.org'
    MATCH_URL = f'{API_BASE}/match/default'
    SEARCH_URL = f'{API_BASE}/search/default'
    TIMEOUT = 20

    HEADERS = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'IBP-OSINT/1.0',
    }

    def __init__(self, timeout: int = 20, min_score: float = 0.5):
        self.timeout = timeout
        self.min_score = min_score
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def check_person(
        self,
        full_name: str,
        birth_date: Optional[str] = None,
        inn: Optional[str] = None,
    ) -> List[OpenSanctionsMatch]:
        """
        Check a person against all OpenSanctions datasets.

        Args:
            full_name: Full name (Russian or Latin)
            birth_date: Optional date of birth (YYYY-MM-DD)
            inn: Optional Russian INN

        Returns:
            List of OpenSanctionsMatch objects for matches above min_score.
        """
        # Try the /match endpoint first (more precise)
        matches = self._match_person(full_name, birth_date)
        if matches is not None:
            return matches

        # Fallback to /search endpoint
        return self._search_person(full_name)

    def _match_person(
        self,
        full_name: str,
        birth_date: Optional[str] = None,
    ) -> Optional[List[OpenSanctionsMatch]]:
        """
        Use the /match/default endpoint for precise name matching.
        POST with entity properties, returns scored matches.
        """
        properties = {'name': [full_name]}
        if birth_date:
            properties['birthDate'] = [birth_date]

        payload = {
            'schema': 'Person',
            'properties': properties,
        }

        try:
            resp = self.session.post(
                self.MATCH_URL,
                json={'queries': {'q': payload}},
                timeout=self.timeout,
            )

            if resp.status_code == 429:
                logger.warning("OpenSanctions rate limited (429)")
                return None
            if resp.status_code >= 500:
                logger.warning(f"OpenSanctions server error ({resp.status_code})")
                return None

            resp.raise_for_status()
            data = resp.json()

            matches = []
            results = data.get('responses', {}).get('q', {}).get('results', [])

            for result in results:
                score = result.get('score', 0)
                if score < self.min_score:
                    continue

                props = result.get('properties', {})
                names = props.get('name', [])
                birth_dates = props.get('birthDate', [])
                countries = props.get('country', [])

                datasets = result.get('datasets', [])
                entity_id = result.get('id', '')

                # Build human-readable match description
                name_str = names[0] if names else 'Unknown'
                datasets_display = [
                    DATASET_NAMES.get(d, d) for d in datasets[:5]
                ]

                match = OpenSanctionsMatch(
                    entity_id=entity_id,
                    name=name_str,
                    score=score,
                    datasets=datasets,
                    countries=countries,
                    birth_date=birth_dates[0] if birth_dates else '',
                    match_details=(
                        f"Совпадение ({score:.0%}): {name_str}. "
                        f"Списки: {', '.join(datasets_display)}"
                    ),
                    url=f'https://opensanctions.org/entities/{entity_id}/',
                    source_name=datasets_display[0] if datasets_display else 'OpenSanctions',
                )
                matches.append(match)

            return matches

        except requests.Timeout:
            logger.warning("OpenSanctions /match timeout")
            return None
        except requests.ConnectionError:
            logger.warning("OpenSanctions connection error")
            return None
        except Exception as e:
            logger.error(f"OpenSanctions /match error: {e}")
            return None

    def _search_person(self, full_name: str) -> List[OpenSanctionsMatch]:
        """
        Fallback: use the /search/default endpoint for text search.
        """
        try:
            resp = self.session.get(
                self.SEARCH_URL,
                params={'q': full_name, 'limit': 20},
                timeout=self.timeout,
            )

            if resp.status_code in (429, 500, 502, 503):
                logger.warning(f"OpenSanctions /search status {resp.status_code}")
                return []

            resp.raise_for_status()
            data = resp.json()

            matches = []
            for result in data.get('results', []):
                score = result.get('score', 0)
                if score < self.min_score:
                    continue

                props = result.get('properties', {})
                names = props.get('name', [])
                datasets = result.get('datasets', [])
                entity_id = result.get('id', '')

                name_str = names[0] if names else 'Unknown'
                datasets_display = [
                    DATASET_NAMES.get(d, d) for d in datasets[:5]
                ]

                match = OpenSanctionsMatch(
                    entity_id=entity_id,
                    name=name_str,
                    score=score,
                    datasets=datasets,
                    countries=props.get('country', []),
                    birth_date=(props.get('birthDate', [''])[0] if props.get('birthDate') else ''),
                    match_details=(
                        f"Совпадение ({score:.0%}): {name_str}. "
                        f"Списки: {', '.join(datasets_display)}"
                    ),
                    url=f'https://opensanctions.org/entities/{entity_id}/',
                    source_name=datasets_display[0] if datasets_display else 'OpenSanctions',
                )
                matches.append(match)

            return matches

        except Exception as e:
            logger.warning(f"OpenSanctions /search error: {e}")
            return []

    def is_reachable(self) -> bool:
        """Check if the OpenSanctions API is reachable."""
        try:
            resp = self.session.get(
                f'{self.API_BASE}/',
                timeout=5,
            )
            return resp.status_code < 500
        except Exception:
            return False
