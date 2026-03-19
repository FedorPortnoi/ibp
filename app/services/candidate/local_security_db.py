"""
Local Security Database — MVD Wanted + Extremist List
======================================================
Queries local JSON databases for wanted persons and extremists.
Replaces geo-blocked Russian government website scrapers with
offline-first local lookups.

Data files:
- data/mvd_wanted.json — MVD wanted persons list
- data/extremist_list.json — Minjust extremist list

Update scripts:
- scripts/update_mvd_list.py
- scripts/update_extremist_list.py

Usage:
    from app.services.candidate.local_security_db import LocalSecurityDB
    db = LocalSecurityDB()
    mvd_matches = db.check_mvd_wanted("Иванов Иван Иванович")
    ext_matches = db.check_extremist_list("Иванов Иван Иванович")
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Default data directory (project_root/data/, 4 levels up from this file)
DATA_DIR = Path(__file__).parent.parent.parent.parent / 'data'


@dataclass
class SecurityMatch:
    """A match from a local security database."""
    source: str  # 'mvd_wanted' or 'extremist_list'
    full_name: str = ''
    birth_date: str = ''
    details: str = ''
    category: str = ''
    article: str = ''
    region: str = ''
    url: str = ''

    def to_dict(self) -> dict:
        return {
            'source': self.source,
            'full_name': self.full_name,
            'birth_date': self.birth_date,
            'details': self.details,
            'category': self.category,
            'article': self.article,
            'region': self.region,
            'url': self.url,
        }

    def to_sanctions_dict(self) -> dict:
        """Convert to SanctionsResult-compatible dict."""
        source_names = {
            'mvd_wanted': 'МВД — розыск',
            'extremist_list': 'Перечень экстремистов',
        }
        urls = {
            'mvd_wanted': 'https://xn--b1aew.xn--p1ai/wanted',
            'extremist_list': 'https://minjust.gov.ru/ru/extremist-materials/',
        }
        return {
            'source_name': source_names.get(self.source, self.source),
            'checked': True,
            'found': True,
            'match_details': (
                f"Найден в базе: {self.full_name}"
                + (f" ({self.details})" if self.details else '')
            ),
            'url': self.url or urls.get(self.source, ''),
            'error': None,
        }


def _normalize_name(name: str) -> str:
    """Normalize a Russian name for comparison."""
    return re.sub(r'\s+', ' ', name.strip().lower())


def _name_matches(query: str, candidate: str) -> bool:
    """
    Check if query name matches candidate name.
    Supports partial matching (last + first name) and full name matching.
    """
    q_parts = _normalize_name(query).split()
    c_parts = _normalize_name(candidate).split()

    if not q_parts or not c_parts:
        return False

    # Full match
    if _normalize_name(query) == _normalize_name(candidate):
        return True

    # Last + first name match (at least 2 parts)
    if len(q_parts) >= 2 and len(c_parts) >= 2:
        if q_parts[0] == c_parts[0] and q_parts[1] == c_parts[1]:
            return True

    return False


class LocalSecurityDB:
    """
    Query local JSON databases for wanted persons and extremists.

    The databases are JSON files stored in data/ directory.
    They can be updated via scripts in scripts/ directory.

    Usage:
        db = LocalSecurityDB()
        mvd = db.check_mvd_wanted("Иванов Иван")
        ext = db.check_extremist_list("Иванов Иван")
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self._mvd_data = None
        self._extremist_data = None

    def _load_mvd_data(self) -> List[dict]:
        """Load MVD wanted list from JSON file."""
        if self._mvd_data is not None:
            return self._mvd_data

        path = self.data_dir / 'mvd_wanted.json'
        if not path.exists():
            logger.info(f"MVD wanted list not found at {path}")
            self._mvd_data = []
            return self._mvd_data

        try:
            with open(path, 'r', encoding='utf-8') as f:
                self._mvd_data = json.load(f)
            logger.info(f"Loaded {len(self._mvd_data)} MVD wanted records")
        except Exception as e:
            logger.error(f"Failed to load MVD wanted list: {e}")
            self._mvd_data = []

        return self._mvd_data

    def _load_extremist_data(self) -> List[dict]:
        """Load extremist list from JSON file."""
        if self._extremist_data is not None:
            return self._extremist_data

        path = self.data_dir / 'extremist_list.json'
        if not path.exists():
            logger.info(f"Extremist list not found at {path}")
            self._extremist_data = []
            return self._extremist_data

        try:
            with open(path, 'r', encoding='utf-8') as f:
                self._extremist_data = json.load(f)
            logger.info(f"Loaded {len(self._extremist_data)} extremist records")
        except Exception as e:
            logger.error(f"Failed to load extremist list: {e}")
            self._extremist_data = []

        return self._extremist_data

    def check_mvd_wanted(self, full_name: str) -> List[SecurityMatch]:
        """
        Check if a person is on the MVD wanted list.

        Args:
            full_name: Full name in Russian ("Фамилия Имя Отчество")

        Returns:
            List of SecurityMatch objects (empty if not found).
        """
        data = self._load_mvd_data()
        matches = []

        for entry in data:
            entry_name = entry.get('full_name', '') or entry.get('name', '')
            if _name_matches(full_name, entry_name):
                matches.append(SecurityMatch(
                    source='mvd_wanted',
                    full_name=entry_name,
                    birth_date=entry.get('birth_date', ''),
                    details=entry.get('details', '') or entry.get('article', ''),
                    category=entry.get('category', 'federal'),
                    article=entry.get('article', ''),
                    region=entry.get('region', ''),
                    url=entry.get('url', 'https://xn--b1aew.xn--p1ai/wanted'),
                ))

        return matches

    def check_extremist_list(self, full_name: str) -> List[SecurityMatch]:
        """
        Check if a person is on the extremist list.

        Args:
            full_name: Full name in Russian ("Фамилия Имя Отчество")

        Returns:
            List of SecurityMatch objects (empty if not found).
        """
        data = self._load_extremist_data()
        matches = []

        for entry in data:
            entry_name = entry.get('full_name', '') or entry.get('name', '')
            if _name_matches(full_name, entry_name):
                matches.append(SecurityMatch(
                    source='extremist_list',
                    full_name=entry_name,
                    birth_date=entry.get('birth_date', ''),
                    details=entry.get('details', '') or entry.get('reason', ''),
                    category=entry.get('category', ''),
                    article=entry.get('article', ''),
                    region=entry.get('region', ''),
                    url=entry.get('url', 'https://minjust.gov.ru/ru/extremist-materials/'),
                ))

        return matches

    def has_mvd_data(self) -> bool:
        """Check if MVD wanted data file exists."""
        return (self.data_dir / 'mvd_wanted.json').exists()

    def has_extremist_data(self) -> bool:
        """Check if extremist list data file exists."""
        return (self.data_dir / 'extremist_list.json').exists()

    def mvd_record_count(self) -> int:
        """Return number of records in MVD wanted list."""
        return len(self._load_mvd_data())

    def extremist_record_count(self) -> int:
        """Return number of records in extremist list."""
        return len(self._load_extremist_data())
