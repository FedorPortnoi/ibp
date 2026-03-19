"""
Checko.ru Service — Enforcement Proceedings & Business Registry
================================================================
Global alternative to FSSP (geo-blocked) for enforcement proceedings.
Checko.ru aggregates data from FSSP, EGRUL, and other Russian registries
and is accessible globally without geo-restrictions.

Usage:
    from app.services.phase3.checko_service import CheckoService
    svc = CheckoService()
    records = svc.search_person("Иванов Иван Иванович")
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}


@dataclass
class CheckoRecord:
    """A record from checko.ru (enforcement proceeding or business)."""
    record_type: str = ''  # 'enforcement' or 'business'
    person_name: str = ''
    proceedings_number: str = ''
    subject: str = ''
    amount: Optional[float] = None
    department: str = ''
    is_active: bool = True
    end_date: Optional[str] = None
    end_reason: Optional[str] = None
    # Business fields
    company_name: str = ''
    inn: str = ''
    ogrn: str = ''
    role: str = ''
    status: str = ''
    source: str = 'checko.ru'

    def to_dict(self) -> dict:
        return {
            'record_type': self.record_type,
            'person_name': self.person_name,
            'proceedings_number': self.proceedings_number,
            'subject': self.subject,
            'amount': self.amount,
            'department': self.department,
            'is_active': self.is_active,
            'end_date': self.end_date,
            'end_reason': self.end_reason,
            'company_name': self.company_name,
            'inn': self.inn,
            'ogrn': self.ogrn,
            'role': self.role,
            'status': self.status,
            'source': self.source,
        }

    def to_fssp_dict(self) -> dict:
        """Convert to FSSP-compatible dict for pipeline integration."""
        return {
            'debtor_name': self.person_name,
            'debtor_dob': '',
            'proceedings_number': self.proceedings_number,
            'document_details': '',
            'subject': self.subject,
            'amount': self.amount,
            'department': self.department,
            'end_date': self.end_date,
            'end_reason': self.end_reason,
            'is_active': self.is_active,
            'source': 'checko.ru',
        }


def _parse_amount(text: str) -> Optional[float]:
    """Parse monetary amount from Russian text."""
    if not text:
        return None
    match = re.search(r'(\d[\d\s\xa0]*\d)(?:[,.](\d{1,2}))?', text)
    if not match:
        match = re.search(r'(\d+)(?:[,.](\d{1,2}))?', text)
    if not match:
        return None
    integer_part = match.group(1).replace(' ', '').replace('\xa0', '')
    decimal_part = match.group(2) or '0'
    try:
        return float(f"{integer_part}.{decimal_part}")
    except ValueError:
        return None


class CheckoService:
    """
    Search checko.ru for enforcement proceedings and business records.

    checko.ru is a free aggregator that provides:
    - FSSP enforcement proceedings data
    - EGRUL business registry data
    - Court records
    All accessible globally without geo-restrictions.

    Usage:
        svc = CheckoService()
        fssp_records = svc.search_enforcement("Иванов Иван Иванович")
        biz_records = svc.search_business("Иванов Иван Иванович")
    """

    BASE_URL = 'https://checko.ru'
    SEARCH_URL = 'https://checko.ru/search'
    TIMEOUT = 25

    def __init__(self, timeout: int = 25):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def search_person(self, full_name: str) -> List[CheckoRecord]:
        """
        Search checko.ru for a person by name.
        Returns combined enforcement + business records.
        """
        records = []
        try:
            records.extend(self.search_enforcement(full_name))
        except Exception as e:
            logger.warning(f"Checko enforcement search error: {e}")
        try:
            records.extend(self.search_business(full_name))
        except Exception as e:
            logger.warning(f"Checko business search error: {e}")
        return records

    def search_enforcement(self, full_name: str) -> List[CheckoRecord]:
        """
        Search checko.ru for FSSP enforcement proceedings.
        Scrapes the person search page.
        """
        try:
            resp = self.session.get(
                self.SEARCH_URL,
                params={'query': full_name},
                timeout=self.timeout,
            )

            if resp.status_code == 403:
                logger.warning("Checko.ru returned 403 (anti-bot)")
                return []
            if resp.status_code == 429:
                logger.warning("Checko.ru rate limit (429)")
                return []

            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or 'utf-8'
            return self._parse_enforcement_results(resp.text, full_name)

        except requests.Timeout:
            logger.warning("Checko.ru timeout")
            return []
        except requests.ConnectionError:
            logger.warning("Checko.ru connection error")
            return []
        except Exception as e:
            logger.error(f"Checko.ru search error: {e}")
            return []

    def search_business(self, full_name: str) -> List[CheckoRecord]:
        """
        Search checko.ru for business registrations.
        """
        try:
            resp = self.session.get(
                self.SEARCH_URL,
                params={'query': full_name},
                timeout=self.timeout,
            )

            if resp.status_code in (403, 429):
                return []

            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or 'utf-8'
            return self._parse_business_results(resp.text, full_name)

        except Exception as e:
            logger.warning(f"Checko.ru business search error: {e}")
            return []

    def _parse_enforcement_results(
        self, html: str, full_name: str,
    ) -> List[CheckoRecord]:
        """Parse enforcement proceedings from checko.ru HTML."""
        records = []
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Look for enforcement proceedings sections
            # Checko shows FSSP data in tables or card-like blocks
            for section in soup.find_all(
                ['div', 'section', 'table'],
                string=re.compile(
                    r'исполнительн|производств|ФССП|взыскани|задолженност',
                    re.IGNORECASE,
                ),
            ):
                text = section.get_text(separator='\n')
                records.extend(self._extract_enforcement_from_text(text, full_name))

            # Also search all tables for ИП-pattern numbers
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                for row in rows:
                    row_text = row.get_text(separator=' ')
                    if re.search(r'\d+/\d+/\d+-ИП', row_text):
                        rec = self._parse_enforcement_row(row, full_name)
                        if rec:
                            records.append(rec)

            # Fallback: search entire page text for ИП patterns
            if not records:
                page_text = soup.get_text(separator='\n')
                records = self._extract_enforcement_from_text(page_text, full_name)

        except Exception as e:
            logger.error(f"Checko enforcement parse error: {e}")

        return records

    def _extract_enforcement_from_text(
        self, text: str, full_name: str,
    ) -> List[CheckoRecord]:
        """Extract enforcement records from freeform text."""
        records = []
        for m in re.finditer(r'(\d+/\d+/[\d\w]+-ИП)', text):
            start = max(0, m.start() - 300)
            end = min(len(text), m.end() + 300)
            ctx = text[start:end]

            amount = _parse_amount(ctx)

            subject = ''
            for pat in [
                r'(?:предмет[^:]*:\s*)(.+?)(?:\n|$)',
                r'((?:задолженность|алимент|штраф|налог|кредит|госпошлин)[^\n]*)',
                r'((?:взыскани)[^\n]*)',
            ]:
                sm = re.search(pat, ctx, re.IGNORECASE)
                if sm:
                    subject = sm.group(1).strip()[:200]
                    break

            department = ''
            dm = re.search(r'(?:отдел|ОСП|РОСП)[^\n]{0,100}', ctx, re.IGNORECASE)
            if dm:
                department = dm.group().strip()[:150]

            end_date = None
            end_reason = None
            em = re.search(
                r'(?:окончан|прекращен|завершен)[^:]*?(\d{2}\.\d{2}\.\d{4})',
                ctx, re.IGNORECASE,
            )
            if em:
                end_date = em.group(1)

            records.append(CheckoRecord(
                record_type='enforcement',
                person_name=full_name,
                proceedings_number=m.group(1),
                subject=subject,
                amount=amount,
                department=department,
                is_active=end_date is None,
                end_date=end_date,
                end_reason=end_reason,
            ))
        return records

    def _parse_enforcement_row(self, row, full_name: str) -> Optional[CheckoRecord]:
        """Parse a table row containing enforcement data."""
        cells = row.find_all('td')
        if len(cells) < 3:
            return None
        row_text = row.get_text(separator=' ')
        ip_match = re.search(r'(\d+/\d+/[\d\w]+-ИП)', row_text)
        if not ip_match:
            return None
        return CheckoRecord(
            record_type='enforcement',
            person_name=full_name,
            proceedings_number=ip_match.group(1),
            subject=cells[-1].get_text(strip=True) if cells else '',
            amount=_parse_amount(row_text),
            is_active=True,
        )

    def _parse_business_results(
        self, html: str, full_name: str,
    ) -> List[CheckoRecord]:
        """Parse business records from checko.ru HTML."""
        records = []
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Look for company cards/links (skip navigation links like /company/select)
            for link in soup.find_all('a', href=re.compile(r'/company/')):
                href = link.get('href', '')
                if '/select' in href or '?' in href:
                    continue
                text = link.get_text(separator=' ').strip()
                if not text or len(text) < 3:
                    continue

                # Extract INN from surrounding context
                parent = link.parent
                parent_text = parent.get_text(separator=' ') if parent else ''
                inn_match = re.search(r'ИНН\s*[:\s]*(\d{10,12})', parent_text)
                ogrn_match = re.search(r'ОГРН\s*[:\s]*(\d{13,15})', parent_text)

                # Detect role
                role = 'Связанное лицо'
                if re.search(r'учредител|участни', parent_text, re.IGNORECASE):
                    role = 'Учредитель'
                elif re.search(r'директор|руководител|генеральн', parent_text, re.IGNORECASE):
                    role = 'Руководитель'
                elif re.search(r'ИП|индивидуальн', parent_text, re.IGNORECASE):
                    role = 'Индивидуальный предприниматель'

                # Status
                status = 'Действующее'
                if re.search(r'ликвидир|прекращ|недействующ', parent_text, re.IGNORECASE):
                    status = 'Ликвидировано'

                records.append(CheckoRecord(
                    record_type='business',
                    person_name=full_name,
                    company_name=text[:200],
                    inn=inn_match.group(1) if inn_match else '',
                    ogrn=ogrn_match.group(1) if ogrn_match else '',
                    role=role,
                    status=status,
                ))

        except Exception as e:
            logger.error(f"Checko business parse error: {e}")

        return records
