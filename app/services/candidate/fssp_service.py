"""
ФССП Service — Enforcement Proceedings Search
===============================================
Searches for enforcement proceedings (исполнительные производства)
via the ФССП system.

Strategy:
1. Try the official API (api-ip.fssp.gov.ru) if FSSP_API_TOKEN is set
2. Try direct AJAX call to is-go.fssp.gov.ru (sometimes returns results
   without CAPTCHA depending on server load/region)
3. Fall back to providing a manual search URL

The public web form at fssp.gov.ru/iss/ip/ always presents a visual
CAPTCHA after submission, so pure Playwright scraping is not viable
for fully automated access.
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from html import unescape
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)


# ── Region name → ФССП region code mapping ──────────────────────────
# Values from fssp.gov.ru/iss/ip/ <select id="region_id">.
# "-1" = all regions.
REGION_CODES = {
    'москва': '77', 'московская': '50', 'московская область': '50',
    'санкт-петербург': '78', 'петербург': '78', 'спб': '78',
    'ленинградская': '47', 'ленинградская область': '47',
    'свердловская': '66', 'екатеринбург': '66',
    'новосибирская': '54', 'новосибирск': '54',
    'нижегородская': '52', 'нижний новгород': '52',
    'самарская': '63', 'самара': '63',
    'ростовская': '61', 'ростов': '61',
    'челябинская': '74', 'челябинск': '74',
    'воронежская': '36', 'воронеж': '36',
    'волгоградская': '34', 'волгоград': '34',
    'краснодарский': '23', 'краснодар': '23',
    'красноярский': '24', 'красноярск': '24',
    'пермский': '59', 'пермь': '59',
    'тюменская': '72', 'тюмень': '72',
    'саратовская': '64', 'саратов': '64',
    'иркутская': '38', 'иркутск': '38',
    'омская': '55', 'омск': '55',
    'калининградская': '39', 'калининград': '39',
    'тульская': '71', 'тула': '71',
    'кемеровская': '42', 'кемерово': '42', 'кузбасс': '42',
    'белгородская': '31', 'белгород': '31',
    'владимирская': '33', 'владимир': '33',
    'ярославская': '76', 'ярославль': '76',
    'тверская': '69', 'тверь': '69',
    'рязанская': '62', 'рязань': '62',
    'курская': '46', 'курск': '46',
    'брянская': '32', 'брянск': '32',
    'архангельская': '29', 'архангельск': '29',
    'мурманская': '51', 'мурманск': '51',
    'оренбургская': '56', 'оренбург': '56',
    'ульяновская': '73', 'ульяновск': '73',
    'пензенская': '58', 'пенза': '58',
    'липецкая': '48', 'липецк': '48',
    'томская': '70', 'томск': '70',
    'астраханская': '30', 'астрахань': '30',
    'калужская': '40', 'калуга': '40',
    'смоленская': '67', 'смоленск': '67',
    'орловская': '57', 'орёл': '57', 'орел': '57',
    'вологодская': '35', 'вологда': '35',
    'курганская': '45', 'курган': '45',
    'костромская': '44', 'кострома': '44',
    'тамбовская': '68', 'тамбов': '68',
    'псковская': '60', 'псков': '60',
    'новгородская': '53', 'великий новгород': '53',
    'кировская': '43', 'киров': '43',
    'амурская': '28', 'благовещенск': '28',
    'сахалинская': '65', 'южно-сахалинск': '65',
    'магаданская': '49', 'магадан': '49',
    'ивановская': '37', 'иваново': '37',
    'татарстан': '16', 'казань': '16',
    'башкортостан': '02', 'уфа': '02',
    'дагестан': '05', 'махачкала': '05',
    'крым': '82', 'севастополь': '82', 'симферополь': '82',
    'удмуртия': '18', 'ижевск': '18',
    'чувашия': '21', 'чебоксары': '21',
    'марий эл': '12', 'йошкар-ола': '12',
    'мордовия': '13', 'саранск': '13',
    'коми': '11', 'сыктывкар': '11',
    'карелия': '10', 'петрозаводск': '10',
    'бурятия': '03', 'улан-удэ': '03',
    'якутия': '14', 'саха': '14', 'якутск': '14',
    'тыва': '17', 'кызыл': '17',
    'хакасия': '19', 'абакан': '19',
    'адыгея': '01', 'майкоп': '01',
    'алтай': '04', 'горно-алтайск': '04',
    'ингушетия': '06', 'магас': '06',
    'кабардино-балкария': '07', 'нальчик': '07',
    'калмыкия': '08', 'элиста': '08',
    'карачаево-черкесия': '09', 'черкесск': '09',
    'северная осетия': '15', 'владикавказ': '15',
    'чечня': '20', 'грозный': '20',
    'приморский': '25', 'владивосток': '25',
    'хабаровский': '27', 'хабаровск': '27',
    'ставропольский': '26', 'ставрополь': '26',
    'забайкальский': '75', 'чита': '75',
    'камчатский': '41', 'камчатка': '41',
    'алтайский': '22', 'барнаул': '22',
    'ханты-мансийский': '86', 'хмао': '86', 'югра': '86',
    'ямало-ненецкий': '89', 'янао': '89',
}


def parse_amount(text: str) -> Optional[float]:
    """
    Parse a monetary amount from Russian ФССП text.

    Handles: "127 432,51 руб.", "45 000 руб.", "3 200,00 р.", "0,00 руб."
    """
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


@dataclass
class FSSPRecord:
    """An enforcement proceeding from ФССП."""
    debtor_name: str = ''
    debtor_dob: str = ''
    proceedings_number: str = ''
    document_details: str = ''
    subject: str = ''
    amount: Optional[float] = None
    department: str = ''
    end_date: Optional[str] = None
    end_reason: Optional[str] = None
    is_active: bool = True
    source: str = 'fssp.gov.ru'

    def to_dict(self) -> dict:
        return {
            'debtor_name': self.debtor_name,
            'debtor_dob': self.debtor_dob,
            'proceedings_number': self.proceedings_number,
            'document_details': self.document_details,
            'subject': self.subject,
            'amount': self.amount,
            'department': self.department,
            'end_date': self.end_date,
            'end_reason': self.end_reason,
            'is_active': self.is_active,
            'source': self.source,
        }


class FSSPService:
    """
    Search ФССП enforcement proceedings.

    Tries the official API first (if FSSP_API_TOKEN is set),
    then attempts the web AJAX endpoint, then falls back to
    providing a manual search URL.

    Usage:
        svc = FSSPService()
        records, manual_url = svc.search("Иванов Иван Иванович", "1985-01-15", "Москва")
    """

    API_BASE = 'https://api-ip.fssp.gov.ru/api/v1.0'
    AJAX_URL = 'https://is-go.fssp.gov.ru/ajax_search'
    WEB_URL = 'https://fssp.gov.ru/iss/ip/'

    HEADERS = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/121.0.0.0 Safari/537.36'
        ),
        'Accept': '*/*',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    }

    def __init__(self, timeout: int = 30, max_pages: int = 3):
        self.timeout = timeout
        self.max_pages = max_pages
        self.api_token = os.environ.get('FSSP_API_TOKEN', '').strip()
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def search(
        self,
        full_name: str,
        date_of_birth: Optional[str] = None,
        region: Optional[str] = None,
    ) -> List[FSSPRecord]:
        """
        Search ФССП for enforcement proceedings.

        Args:
            full_name: "Фамилия Имя Отчество"
            date_of_birth: "YYYY-MM-DD" or "DD.MM.YYYY"
            region: Region name (e.g. "Москва")

        Returns:
            List of FSSPRecord (may be empty if CAPTCHA blocks access)
        """
        parts = full_name.strip().split()
        if len(parts) < 2:
            logger.warning(f"ФССП: need at least 2 name parts, got: {full_name}")
            return []

        last_name = parts[0]
        first_name = parts[1]
        patronymic = parts[2] if len(parts) > 2 else ''
        dob = self._format_dob(date_of_birth) if date_of_birth else ''
        region_code = self._resolve_region(region)

        # Strategy 1: Official API
        if self.api_token:
            try:
                records = self._search_api(
                    last_name, first_name, patronymic, dob, region_code,
                )
                if records is not None:  # None = API error; [] = no results
                    return records
            except Exception as e:
                logger.warning(f"ФССП API error: {e}")

        # Strategy 2: Direct AJAX call (may hit CAPTCHA)
        try:
            records = self._search_ajax(
                last_name, first_name, patronymic, dob, region_code,
            )
            if records is not None:
                return records
        except Exception as e:
            logger.warning(f"ФССП AJAX error: {e}")

        # Strategy 3: Return manual URL as a record
        logger.info("ФССП: automated search blocked by CAPTCHA, providing manual URL")
        return self._manual_fallback(last_name, first_name, patronymic, dob, region_code)

    def get_manual_url(
        self,
        full_name: str,
        date_of_birth: Optional[str] = None,
        region: Optional[str] = None,
    ) -> str:
        """Generate a direct URL to the ФССП search page."""
        return self.WEB_URL

    # ── API approach ──────────────────────────────────────────────

    def _search_api(
        self, last_name, first_name, patronymic, dob, region_code,
    ) -> Optional[List[FSSPRecord]]:
        """
        Official ФССП API: 2-step (submit search → poll result).
        Returns None on API failure, [] on no results.
        """
        params = {
            'token': self.api_token,
            'region': region_code or '',
            'lastname': last_name,
            'firstname': first_name,
        }
        if patronymic:
            params['secondname'] = patronymic
        if dob:
            params['birthdate'] = dob

        # Step 1: submit search
        try:
            r = self.session.get(
                f'{self.API_BASE}/search/physical',
                params=params,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            logger.warning(f"ФССП API request failed: {e}")
            return None

        if r.status_code != 200:
            logger.warning(f"ФССП API status {r.status_code}")
            return None

        try:
            data = r.json()
        except (ValueError, KeyError):
            logger.warning("ФССП API: invalid JSON response")
            return None

        if data.get('exception'):
            logger.warning(f"ФССП API exception: {data['exception']}")
            return None

        task_id = data.get('response', {}).get('task')
        if not task_id:
            logger.warning("ФССП API: no task_id in response")
            return None

        # Step 2: poll for results (up to 30s)
        for _ in range(10):
            time.sleep(3)
            try:
                r2 = self.session.get(
                    f'{self.API_BASE}/result',
                    params={'token': self.api_token, 'task': task_id},
                    timeout=self.timeout,
                )
                if r2.status_code != 200:
                    continue

                result = r2.json()
                status = result.get('response', {}).get('status')

                if status == 0:  # completed
                    return self._parse_api_results(result)
                elif status == 1:  # still processing
                    continue
                else:
                    logger.warning(f"ФССП API task status: {status}")
                    return None

            except Exception as e:
                logger.warning(f"ФССП API poll error: {e}")
                continue

        logger.warning("ФССП API: task polling timed out")
        return None

    def _parse_api_results(self, data: dict) -> List[FSSPRecord]:
        """Parse the official API response into FSSPRecord objects."""
        records = []
        result_list = data.get('response', {}).get('result', [])

        for group in result_list:
            for item in group.get('result', []):
                subject = item.get('exe_production', '')
                amount = parse_amount(subject)

                end_date = item.get('ip_end') or None
                end_reason = None
                if end_date:
                    # ip_end may contain date + reason
                    dm = re.search(r'(\d{2}\.\d{2}\.\d{4})', end_date)
                    if dm:
                        end_reason = end_date[dm.end():].strip()
                        end_date = dm.group(1)

                records.append(FSSPRecord(
                    debtor_name=item.get('name', ''),
                    debtor_dob=item.get('birthdate', ''),
                    proceedings_number=item.get('ip_number', ''),
                    document_details=item.get('ip_document', ''),
                    subject=subject,
                    amount=amount,
                    department=item.get('department', ''),
                    end_date=end_date,
                    end_reason=end_reason,
                    is_active=not bool(end_date),
                    source='api-ip.fssp.gov.ru',
                ))

        return records

    # ── Web AJAX approach ────────────────────────────────────────

    def _search_ajax(
        self, last_name, first_name, patronymic, dob, region_code,
    ) -> Optional[List[FSSPRecord]]:
        """
        Try the web AJAX endpoint directly.
        Returns None if CAPTCHA blocks the response.
        Returns [] if no results found.
        """
        # Visit main page first to establish cookies
        try:
            self.session.get(self.WEB_URL, timeout=10)
        except requests.RequestException:
            pass

        time.sleep(1)

        params = {
            'system': 'ip',
            'is[extended]': '1',
            'nocache': '1',
            'is[variant]': '1',
            'is[last_name]': last_name,
            'is[first_name]': first_name,
        }
        if patronymic:
            params['is[patronymic]'] = patronymic
        if dob:
            params['is[date]'] = dob
        if region_code:
            params['is[region_id][0]'] = region_code

        self.session.headers['Referer'] = self.WEB_URL

        try:
            r = self.session.get(
                self.AJAX_URL,
                params=params,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            logger.warning(f"ФССП AJAX request failed: {e}")
            return None

        if r.status_code != 200:
            return None

        text = r.text.strip()

        # Response is JSONP: ({"data":"<html>","err":"","e":""});
        if text.startswith('(') and text.endswith(');'):
            text = text[1:-2]
        elif text.startswith('(') and text.endswith(')'):
            text = text[1:-1]

        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            logger.warning("ФССП AJAX: cannot parse JSONP response")
            return None

        html = unescape(payload.get('data', ''))

        # Check for CAPTCHA
        if 'captcha-popup' in html and 'display: block' in html:
            logger.info("ФССП AJAX: CAPTCHA required")
            return None  # Signal to fall back to manual

        # Check for "no results"
        if not html or 'Ничего не найдено' in html or len(html) < 100:
            return []

        # Parse the HTML results
        return self._parse_ajax_html(html)

    def _parse_ajax_html(self, html: str) -> List[FSSPRecord]:
        """Parse results HTML from the AJAX response."""
        records = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
        except ImportError:
            # Fallback to regex parsing
            return self._parse_html_regex(html)

        # ФССП results come as a table with specific columns
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 2:
                continue
            header = rows[0].get_text().lower()
            if any(kw in header for kw in ['должник', 'производств', 'предмет']):
                for row in rows[1:]:
                    rec = self._parse_table_row(row)
                    if rec:
                        records.append(rec)
                if records:
                    return records

        # Try div-based result blocks
        for block in soup.select('.iss-result, .result-item, [class*="result"]'):
            text = block.get_text(separator='\n')
            if 'должник' in text.lower() or re.search(r'\d+/\d+/\d+-ИП', text):
                rec = self._parse_text_block(text)
                if rec:
                    records.append(rec)

        # Freeform: find ИП numbers in text
        if not records:
            records = self._parse_html_regex(html)

        return records

    def _parse_table_row(self, row) -> Optional[FSSPRecord]:
        """Parse a results table row (7 columns typical for ФССП)."""
        cells = row.find_all('td')
        if len(cells) < 4:
            return None
        texts = [c.get_text(strip=True) for c in cells]

        # Column layout: #, Debtor, ИП number, Document, End info, Subject+amount, Department
        debtor_cell = texts[1] if len(texts) > 1 else ''
        debtor_name, debtor_dob = self._split_name_dob(debtor_cell)

        proceedings = texts[2] if len(texts) > 2 else ''
        ip_match = re.search(r'(\d+/\d+/[\d\w]+-ИП)', proceedings)
        proceedings_number = ip_match.group(1) if ip_match else proceedings.strip()

        document_details = texts[3] if len(texts) > 3 else ''

        end_cell = texts[4] if len(texts) > 4 else ''
        end_date, end_reason = self._parse_end_info(end_cell)

        subject_cell = texts[5] if len(texts) > 5 else ''
        amount = parse_amount(subject_cell)

        department = texts[6] if len(texts) > 6 else ''

        if not proceedings_number and not debtor_name:
            return None

        return FSSPRecord(
            debtor_name=debtor_name,
            debtor_dob=debtor_dob,
            proceedings_number=proceedings_number,
            document_details=document_details,
            subject=subject_cell,
            amount=amount,
            department=department,
            end_date=end_date,
            end_reason=end_reason,
            is_active=end_date is None and not end_reason,
        )

    def _parse_text_block(self, text: str) -> Optional[FSSPRecord]:
        """Parse a freeform text block into an FSSPRecord."""
        ip_match = re.search(r'(\d+/\d+/[\d\w]+-ИП)', text)
        proceedings_number = ip_match.group(1) if ip_match else ''

        debtor_name = debtor_dob = ''
        name_m = re.search(
            r'([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)'
            r'\s*,?\s*(\d{2}\.\d{2}\.\d{4})?',
            text,
        )
        if name_m:
            debtor_name = name_m.group(1)
            debtor_dob = name_m.group(2) or ''

        amount = parse_amount(text)
        subject = ''
        for pat in [
            r'(?:предмет[^:]*:\s*)(.+?)(?:\n|$)',
            r'((?:задолженность|алимент|штраф|налог|кредит|госпошлин)[^\n]*)',
        ]:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                subject = m.group(1).strip()
                break

        end_date = None
        end_m = re.search(
            r'(?:окончан|прекращен)[^:]*:\s*(\d{2}\.\d{2}\.\d{4})',
            text, re.IGNORECASE,
        )
        if end_m:
            end_date = end_m.group(1)

        if not proceedings_number and not debtor_name and not subject:
            return None

        return FSSPRecord(
            debtor_name=debtor_name,
            debtor_dob=debtor_dob,
            proceedings_number=proceedings_number,
            subject=subject,
            amount=amount,
            end_date=end_date,
            is_active=end_date is None,
        )

    def _parse_html_regex(self, html: str) -> List[FSSPRecord]:
        """Last-resort regex parser for ИП numbers in raw HTML."""
        records = []
        for m in re.finditer(r'(\d+/\d+/\d+-ИП)', html):
            start = max(0, m.start() - 500)
            end = min(len(html), m.end() + 500)
            ctx = html[start:end]

            name_m = re.search(
                r'([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
                ctx,
            )
            records.append(FSSPRecord(
                debtor_name=name_m.group(1) if name_m else '',
                proceedings_number=m.group(1),
                amount=parse_amount(ctx),
                is_active=True,
            ))
        return records

    # ── Manual fallback ──────────────────────────────────────────

    def _manual_fallback(
        self, last_name, first_name, patronymic, dob, region_code,
    ) -> List[FSSPRecord]:
        """Return a placeholder record with manual search instructions."""
        return [FSSPRecord(
            debtor_name=f'{last_name} {first_name} {patronymic}'.strip(),
            proceedings_number='Требуется ручная проверка',
            subject=(
                'Автоматический поиск заблокирован CAPTCHA. '
                'Проверьте вручную: fssp.gov.ru/iss/ip/'
            ),
            is_active=False,
            source='manual',
        )]

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _format_dob(dob: str) -> str:
        """Convert YYYY-MM-DD → DD.MM.YYYY."""
        dob = dob.strip()
        if re.match(r'^\d{2}\.\d{2}\.\d{4}$', dob):
            return dob
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', dob)
        if m:
            return f"{m.group(3)}.{m.group(2)}.{m.group(1)}"
        return dob

    @staticmethod
    def _resolve_region(region: Optional[str]) -> Optional[str]:
        """Map region name to ФССП region code."""
        if not region:
            return None
        region_lower = region.lower().strip()
        for prefix in ['г. ', 'г.', 'город ', 'обл. ', 'обл.', 'область ']:
            if region_lower.startswith(prefix):
                region_lower = region_lower[len(prefix):].strip()
        for key, code in REGION_CODES.items():
            if key in region_lower or region_lower in key:
                return code
        return '-1'

    @staticmethod
    def _split_name_dob(text: str):
        """Split "Иванов Иван Иванович, 15.01.1985" into name and dob."""
        m = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
        if m:
            name = text[:m.start()].strip().rstrip(',').strip()
            return name, m.group(1)
        return text.strip(), ''

    @staticmethod
    def _parse_end_info(text: str):
        """Parse end date + reason from a cell."""
        text = text.strip()
        if not text or text == '—':
            return None, None
        m = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
        if m:
            reason = text[m.end():].strip().lstrip(',').strip()
            return m.group(1), reason or None
        return None, text if text else None
