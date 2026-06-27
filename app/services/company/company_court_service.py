"""
Company Court Search — Arbitration + General Jurisdiction
==========================================================
Sources:
  1. reputation.su        — 58M+ cases, globally accessible, no auth
  2. судебныерешения.рф   — general jurisdiction (PHP session search,
                            accessible from Russian IPs; times out from abroad)

Manual fallback URLs provided for kad.arbitr.ru (geo-blocked), sudact.ru,
casebook.ru (requires login), and ГАС Правосудие.

Usage:
    svc = CompanyCourtSearch()
    cases = svc.search(company_name="ООО Ромашка", inn="7701234567")
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Dict

import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from app.services.shared.court_utils import COURT_CATEGORY_MAP, get_li_value

logger = logging.getLogger(__name__)

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}

_PLAINTIFF_KW = ('истец', 'заявитель', 'взыскатель')
_DEFENDANT_KW = ('ответчик',)



@dataclass
class CompanyCourtCase:
    case_number: str
    court_name: str = ""
    case_type: str = ""   # арбитражное | гражданское | административное | банкротное | уголовное
    date: str = ""
    role: str = ""        # истец | ответчик | должник | третье лицо
    subject: str = ""
    result: str = ""
    parties: str = ""
    url: str = ""
    source: str = ""

    def to_dict(self) -> Dict:
        return {
            'case_number': self.case_number,
            'court_name': self.court_name,
            'case_type': self.case_type,
            'date': self.date,
            'role': self.role,
            'subject': self.subject,
            'result': self.result,
            'parties': self.parties,
            'url': self.url,
            'source': self.source,
        }


class CompanyCourtSearch:
    """Search Russian court records for a company by name and/or INN."""

    _SR_BASE = 'https://xn--90afdbaav0bd1afy6eub5d.xn--p1ai'  # судебныерешения.рф

    def __init__(self, timeout: int = 25):
        self.timeout = timeout
        # судебныерешения.рф times out from non-Russian IPs; cap at 15s so it
        # fails fast and doesn't block the reputation.su results.
        self._sr_timeout = min(timeout, 15)
        self._rep_timeout = 35
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)

    # ── Public ──────────────────────────────────────────────────────────────

    def search(
        self,
        company_name: str,
        inn: str = "",
        limit: int = 50,
    ) -> List[CompanyCourtCase]:
        """
        Search court records for a company.

        Sources:
          0. DataNewton /v1/arbitration-cases — arbitration courts (replaces kad.arbitr.ru)
          1. DataNewton /v1/courtCases        — general jurisdiction courts (replaces судебныерешения.рф)
          2. reputation.su                    — supplementary, globally accessible
        Deduplicates by case number across sources.
        """
        results: List[CompanyCourtCase] = []

        # Source 0: parser-api.com (kad.arbitr.ru proxy — works from any IP, no 451)
        arb: List[CompanyCourtCase] = []
        if inn:
            try:
                pa = self._search_parser_api_arbitr(inn, company_name)
                results.extend(pa)
                arb = pa
                logger.info("Company courts parser-api (kad.arbitr) → %d cases", len(pa))
            except Exception as exc:
                logger.warning("Company courts parser-api arbitr failed: %s", exc)

        # Source 0b: direct kad.arbitr.ru (Russian residential IP only, fallback)
        if not arb:
            try:
                kad = self._search_kad_arbitr(company_name, inn)
                results.extend(kad)
                arb = kad
                logger.info("Company courts kad.arbitr.ru → %d cases", len(kad))
            except Exception as exc:
                logger.warning("Company courts kad.arbitr.ru failed: %s", exc)

        if not arb and inn:
            # Both arbitr sources failed — fall back to DataNewton arbitration
            try:
                from app.services.company.datanewton_service import lookup_arbitration_cases
                dn_arb = lookup_arbitration_cases(inn, limit=limit)
                for c in dn_arb:
                    results.append(CompanyCourtCase(**{k: c.get(k, '') for k in CompanyCourtCase.__dataclass_fields__}))
                logger.info("Company courts DataNewton arbitration (fallback) → %d cases", len(dn_arb))
            except Exception as exc:
                logger.warning("Company courts DataNewton arbitration fallback failed: %s", exc)

        # Source 1: DataNewton general jurisdiction courts (СОЮ) — no free alternative
        if inn:
            try:
                from app.services.company.datanewton_service import lookup_court_cases
                sou = lookup_court_cases(inn, limit=limit)
                for c in sou:
                    results.append(CompanyCourtCase(**{k: c[k] for k in CompanyCourtCase.__dataclass_fields__}))
                logger.info("Company courts DataNewton СОЮ → %d cases", len(sou))
            except Exception as exc:
                logger.warning("Company courts DataNewton СОЮ failed: %s", exc)

        # Source 2: reputation.su (supplementary — skip if parser-api already has enough)
        if len(results) < 20:
            try:
                rep = self._search_reputation_su(company_name, inn)
                results.extend(rep)
                logger.info("Company courts reputation.su → %d cases", len(rep))
            except Exception as exc:
                logger.warning("Company courts reputation.su failed: %s", exc)

        # Deduplicate
        seen: set = set()
        unique: List[CompanyCourtCase] = []
        for case in results:
            key = case.case_number.strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(case)
            elif not key:
                unique.append(case)

        logger.info("Company courts: %d unique cases for '%s'", len(unique), company_name)
        return unique[:limit]

    @staticmethod
    def get_manual_search_urls(company_name: str, inn: str = "") -> List[Dict]:
        """Manual fallback URLs for the investigator to open in a browser."""
        enc_name = quote(company_name)
        enc_inn = quote(inn) if inn else enc_name
        return [
            {
                'name': 'Картотека арбитражных дел (kad.arbitr.ru)',
                'url': 'https://kad.arbitr.ru/',
                'description': (
                    f'Официальная картотека — введите «{company_name}»'
                    + (f' или ИНН «{inn}»' if inn else '')
                    + ' в поле «Участники». Требует российский IP (HTTP 451 без VPN).'
                ),
            },
            {
                'name': 'Reputation.su',
                'url': f'https://reputation.su/search?query={enc_inn or enc_name}',
                'description': '58M+ судебных дел, доступен без VPN',
            },
            {
                'name': 'Casebook (требует вход)',
                'url': f'https://casebook.ru/search?query={enc_inn}',
                'description': 'Агрегатор арбитражных дел — требует регистрацию',
            },
            {
                'name': 'Судебные акты (sudact.ru)',
                'url': f'https://sudact.ru/regular/doc/?regular-txt={enc_name}',
                'description': 'Суды общей юрисдикции — поиск по названию организации',
            },
            {
                'name': 'ГАС Правосудие',
                'url': 'https://bsr.sudrf.ru/bigs/portal.html',
                'description': 'Суды общей юрисдикции — полнотекстовый поиск по всем регионам',
            },
        ]

    # ── Sources ─────────────────────────────────────────────────────────────

    @staticmethod
    def _kad_name_variants(company_name: str) -> List[str]:
        """
        Build search-friendly name variants for kad.arbitr.ru.

        kad.arbitr.ru stores full legal names in CAPS exactly as in EGRUL,
        e.g. ПУБЛИЧНОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО "ГАЗПРОМ". A query for just
        "ГАЗПРОМ" (bare name) returns the same results and is more reliable
        when the legal form spelling differs.

        Returns up to 3 variants in priority order:
          1. No quotes — removes « » " ' from the original
          2. Short form + bare — ООО РОМАШКА, ПАО ГАЗПРОМ, etc.
          3. Bare name only — the distinctive part without any legal prefix
        """
        if not company_name:
            return []

        # Step 1: strip quotes
        no_quotes = re.sub(r'[«»"""\'„]', '', company_name).strip()
        no_quotes = re.sub(r'\s{2,}', ' ', no_quotes)

        # Full legal form → short abbreviation
        _FORM_MAP = [
            (r'ПУБЛИЧНОЕ\s+АКЦИОНЕРНОЕ\s+ОБЩЕСТВО',         'ПАО'),
            (r'НЕПУБЛИЧНОЕ\s+АКЦИОНЕРНОЕ\s+ОБЩЕСТВО',       'АО'),
            (r'ЗАКРЫТОЕ\s+АКЦИОНЕРНОЕ\s+ОБЩЕСТВО',          'ЗАО'),
            (r'ОТКРЫТОЕ\s+АКЦИОНЕРНОЕ\s+ОБЩЕСТВО',          'ОАО'),
            (r'АКЦИОНЕРНОЕ\s+ОБЩЕСТВО',                     'АО'),
            (r'ОБЩЕСТВО\s+С\s+ОГРАНИЧЕННОЙ\s+ОТВЕТСТВЕННОСТЬЮ', 'ООО'),
            (r'АКЦИОНЕРНЫЙ\s+КОММЕРЧЕСКИЙ\s+БАНК',         'АКБ'),
            (r'КОММЕРЧЕСКИЙ\s+БАНК',                        'КБ'),
            (r'СТРАХОВАЯ\s+КОМПАНИЯ',                       'СК'),
        ]

        bare = no_quotes
        short_prefix = ''
        for pattern, abbr in _FORM_MAP:
            m = re.search(pattern, bare, re.IGNORECASE)
            if m:
                bare = (bare[:m.start()] + bare[m.end():]).strip()
                bare = re.sub(r'\s{2,}', ' ', bare)
                short_prefix = abbr
                break
        # Also strip remaining short-form prefixes sitting at the front
        bare = re.sub(
            r'^(?:ПАО|ОАО|ЗАО|АО|ООО|ИП|НАО|АКБ|КБ|СК)\s+',
            '', bare, flags=re.IGNORECASE
        ).strip()

        variants: List[str] = []

        # Variant 1: no quotes (closest to original, often enough)
        if no_quotes and no_quotes != company_name:
            variants.append(no_quotes)
        else:
            variants.append(company_name)

        # Variant 2: short prefix + bare  (e.g. "ПАО ГАЗПРОМ")
        if short_prefix and bare:
            short_form = f'{short_prefix} {bare}'
            if short_form not in variants:
                variants.append(short_form)

        # Variant 3: bare name only  (e.g. "ГАЗПРОМ")
        if bare and bare not in variants:
            variants.append(bare)

        # Deduplicate while preserving order, cap at 3
        seen: set = set()
        result: List[str] = []
        for v in variants:
            v = v.strip()
            if v and v not in seen:
                seen.add(v)
                result.append(v)
            if len(result) == 3:
                break
        return result

    def _search_parser_api_arbitr(
        self, inn: str, company_name: str
    ) -> List[CompanyCourtCase]:
        """Search kad.arbitr.ru via parser-api.com proxy (works from any IP)."""
        from app.services.parser_api import arbitr_search, is_available
        if not is_available():
            return []

        cases, status = arbitr_search(inn, max_pages=3)
        if status not in ('ok',) or not cases:
            return []

        inn_lower = inn.lower()
        name_lower = company_name.lower()
        records: List[CompanyCourtCase] = []

        for item in cases:
            case_number = item.get('CaseNumber') or ''

            # Role: match INN or name against Plaintiffs/Respondents
            role = ''
            for p in (item.get('Plaintiffs') or []):
                if (p.get('Inn') or '').lower() == inn_lower or name_lower in (p.get('Name') or '').lower():
                    role = 'истец'
                    break
            if not role:
                for p in (item.get('Respondents') or []):
                    if (p.get('Inn') or '').lower() == inn_lower or name_lower in (p.get('Name') or '').lower():
                        role = 'ответчик'
                        break

            # Date: "2023-11-15T00:00:00" → "15.11.2023"
            raw_date = item.get('StartDate') or ''
            date = ''
            if len(raw_date) >= 10:
                parts = raw_date[:10].split('-')
                if len(parts) == 3:
                    date = f"{parts[2]}.{parts[1]}.{parts[0]}"

            subj = item.get('Subject') or ''
            case_type_raw = (item.get('CaseType') or '').lower()
            case_type = 'банкротное' if 'банкрот' in case_type_raw or 'банкрот' in subj.lower() else 'арбитражное'

            case_id = item.get('CaseId') or ''
            url = f'https://kad.arbitr.ru/Card/{case_id}' if case_id else ''

            records.append(CompanyCourtCase(
                case_number=case_number,
                court_name=item.get('Court') or '',
                case_type=case_type,
                date=date,
                role=role,
                subject=subj,
                url=url,
                source='parser-api.com (kad.arbitr.ru)',
            ))

        return records

    def _search_kad_arbitr(
        self, company_name: str, inn: str = ""
    ) -> List[CompanyCourtCase]:
        """
        Search kad.arbitr.ru — the official Russian arbitration court database.

        Requires a Russian IP (returns HTTP 451 geo-block otherwise).
        Runs from Yandex Cloud VM; silently returns [] from dev machines.

        Strategy:
          1. INN query first (10-digit company INN → exact match, most reliable).
             If it returns results, skip all name queries to avoid duplicates.
          2. Name variants in order (no-quotes → short-form → bare).
             Stops after the first variant that returns at least one result.
          3. HTTP 451 at any point → return immediately (no point continuing).
        """
        _KAD_BASE = 'https://kad.arbitr.ru'
        _KAD_HEADERS = {
            **_HEADERS,
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
            'x-date-format': 'iso',
            'Origin': _KAD_BASE,
            'Referer': f'{_KAD_BASE}/',
        }
        _SIDE_TYPES = {1: 'ответчик', 2: 'истец', 3: 'заявитель', 4: 'третье лицо'}

        records: List[CompanyCourtCase] = []
        seen_numbers: set = set()

        # Establish session cookies — kad.arbitr.ru rejects AJAX without them
        try:
            init = self.session.get(f'{_KAD_BASE}/', timeout=10)
            if init.status_code == 451:
                logger.info("kad.arbitr.ru: HTTP 451 on init — not a Russian IP")
                return []
        except Exception as exc:
            logger.warning("kad.arbitr.ru: session init failed: %s", exc)
            return []

        def _fetch_pages(side_dict: dict) -> bool:
            """
            Fetch up to 3 pages for one search query.
            Returns True  → success (may have added records).
            Returns False → geo-blocked (451), caller should abort all queries.
            Returns None  → transient error, try next variant.
            """
            for page in range(1, 4):
                try:
                    payload = {
                        'Sides': [side_dict],
                        'Page': page,
                        'Count': 25,
                        'DateFrom': None,
                        'DateTo': None,
                        'CaseType': 0,
                        'CourtType': -1,
                        'Courts': [],
                        'Judges': [],
                        'CaseNumbers': [],
                        'OrderBy': 'Data',
                        'OrderDirection': 'Desc',
                    }
                    resp = self.session.post(
                        f'{_KAD_BASE}/Kad/SearchInstances',
                        json=payload,
                        timeout=self.timeout,
                        headers=_KAD_HEADERS,
                    )

                    if resp.status_code == 451:
                        logger.info("kad.arbitr.ru: HTTP 451 — not a Russian IP")
                        return False  # caller must abort

                    if resp.status_code == 429:
                        logger.warning("kad.arbitr.ru: rate-limited (429)")
                        return True  # keep what we have

                    if resp.status_code != 200:
                        logger.warning("kad.arbitr.ru: HTTP %d", resp.status_code)
                        return True

                    data = resp.json()
                    result_block = data.get('Result') or data.get('result') or {}
                    items = result_block.get('Items') or result_block.get('items') or []

                    if not items:
                        return True  # no more pages

                    for item in items:
                        case_number = item.get('CaseNumber') or item.get('caseNumber') or ''
                        if not case_number or case_number in seen_numbers:
                            continue
                        seen_numbers.add(case_number)

                        # Date: ISO → DD.MM.YYYY
                        raw_date = item.get('DateTime') or item.get('dateTime') or ''
                        date = ''
                        if raw_date and len(raw_date) >= 10:
                            d = raw_date[:10]  # "2023-11-15"
                            parts = d.split('-')
                            if len(parts) == 3:
                                date = f"{parts[2]}.{parts[1]}.{parts[0]}"

                        # Role: match company in Sides array by name or INN
                        role = ''
                        identifiers = [s.lower() for s in filter(None, [company_name, inn])]
                        # Also match name variants so roles are found even for bare names
                        for variant in self._kad_name_variants(company_name):
                            identifiers.append(variant.lower())
                        for s in (item.get('Sides') or []):
                            side_name = (s.get('Name') or '').lower()
                            side_inn_val = (s.get('Inn') or '').lower()
                            if any(
                                ident and (ident in side_name or ident == side_inn_val)
                                for ident in identifiers
                            ):
                                st = s.get('SideType') or {}
                                st_id = st.get('Id') if isinstance(st, dict) else None
                                role = _SIDE_TYPES.get(
                                    st_id,
                                    st.get('Name', '') if isinstance(st, dict) else ''
                                )
                                break

                        subj = item.get('Subject') or ''
                        case_type = (
                            'банкротное' if 'банкрот' in subj.lower()
                            else 'арбитражное'
                        )
                        case_id = item.get('CaseId') or item.get('caseId') or ''
                        url = f'{_KAD_BASE}/Card/{case_id}' if case_id else ''

                        records.append(CompanyCourtCase(
                            case_number=case_number,
                            court_name=item.get('CourtName') or item.get('courtName') or '',
                            case_type=case_type,
                            date=date,
                            role=role,
                            subject=subj,
                            url=url,
                            source='kad.arbitr.ru',
                        ))

                    total = result_block.get('TotalCount') or result_block.get('totalCount') or 0
                    if page * 25 >= total:
                        return True  # all pages fetched

                except requests.Timeout:
                    logger.warning("kad.arbitr.ru: timeout on page %d", page)
                    return True
                except Exception as exc:
                    logger.warning("kad.arbitr.ru: error on page %d: %s", page, exc)
                    return True

            return True

        # ── Query 1: INN (company only — 10 digits) ──────────────────────
        if inn and len(inn) == 10:
            before = len(records)
            ok = _fetch_pages({'Inn': inn, 'Name': '', 'Type': -1})
            if ok is False:
                return []  # geo-blocked
            if len(records) > before:
                # INN returned results → skip name queries to avoid duplicates
                logger.info("kad.arbitr.ru: INN query found %d cases", len(records))
                return records

        # ── Query 2: name variants (stop at first successful variant) ────
        for variant in self._kad_name_variants(company_name):
            before = len(records)
            ok = _fetch_pages({'Inn': '', 'Name': variant, 'Type': -1})
            if ok is False:
                return records  # geo-blocked mid-run, return what we have
            if len(records) > before:
                logger.info(
                    "kad.arbitr.ru: name variant '%s' found %d cases",
                    variant, len(records) - before,
                )
                break  # found results with this variant, no need to try others

        logger.info("kad.arbitr.ru: %d total cases for '%s'", len(records), company_name)
        return records

    def _search_reputation_su(
        self, company_name: str, inn: str = ""
    ) -> List[CompanyCourtCase]:
        """
        Search reputation.su for company court cases.

        Tries INN query first (cleaner results), then company name.
        Parses the same srch-card__affairs-box elements as the person pipeline.
        """
        queries = []
        if inn and len(inn) in (10, 12):
            queries.append(inn)
        queries.append(company_name)

        records: List[CompanyCourtCase] = []
        seen_numbers: set = set()

        for query in queries:
            try:
                url = f'https://reputation.su/search?query={quote(query)}'
                resp = self.session.get(url, timeout=self._rep_timeout)
                if resp.status_code != 200:
                    logger.warning("reputation.su HTTP %d for '%s'", resp.status_code, query)
                    continue

                parsed = self._parse_reputation_cards(resp.text, company_name, inn)
                for case in parsed:
                    key = case.case_number.strip()
                    if key and key not in seen_numbers:
                        seen_numbers.add(key)
                        records.append(case)
                    elif not key:
                        records.append(case)

                logger.debug(
                    "reputation.su: %d cases for query '%s'", len(parsed), query
                )

            except requests.Timeout:
                logger.warning("reputation.su timeout for '%s'", query)
            except Exception as exc:
                logger.warning("reputation.su error for '%s': %s", query, exc)

        return records

    def _parse_reputation_cards(
        self, html: str, company_name: str, inn: str
    ) -> List[CompanyCourtCase]:
        """Parse srch-card__affairs-box cards from reputation.su HTML."""
        soup = BeautifulSoup(html, 'lxml')
        cards = soup.select('div.srch-card__affairs-box')
        cases: List[CompanyCourtCase] = []

        for card in cards[:20]:
            h3 = card.select_one('h3')
            if not h3:
                continue

            raw = h3.get_text(strip=True)
            m = re.match(r'(\d{1,2}[А-Яа-я]{0,3}-\d+/\d{4})', raw)
            case_number = m.group(1) if m else raw

            # Category → case_type
            category = get_li_value(card, 'Категория').lower()
            case_type = COURT_CATEGORY_MAP.get(category, self._normalize_case_type(category))

            # Date
            date_text = get_li_value(card, 'Регистрация')
            dm = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_text)
            date = dm.group(1) if dm else ''

            # Subject
            subject = get_li_value(card, 'Предмет') or get_li_value(card, 'Суть дела')
            if not subject:
                desc = card.select_one('p.srch-card__description, p.srch-card__subject')
                if desc:
                    subject = desc.get_text(strip=True)[:300]

            # Role
            role = self._detect_company_role(card, company_name, inn)

            # Court
            court_name = get_li_value(card, 'Суд') or get_li_value(card, 'Наименование суда')
            if not court_name:
                ct = re.search(
                    r'([А-ЯЁ][а-яёА-ЯЁ\s\-]{3,80}(?:арбитражный суд|районный суд|городской суд|суд)[а-яёА-ЯЁ\s\-]{0,60})',
                    card.get_text(' ', strip=True),
                    re.IGNORECASE,
                )
                court_name = ct.group(1).strip()[:200] if ct else ''

            # URL
            url = ''
            for a in card.select('a[href*="/sudrf/"]'):
                href = a.get('href', '')
                if '/participant' not in href:
                    url = f'https://reputation.su{href}' if href.startswith('/') else href
                    break

            cases.append(CompanyCourtCase(
                case_number=case_number,
                court_name=court_name,
                case_type=case_type,
                date=date,
                role=role,
                subject=subject,
                result=get_li_value(card, 'Статус'),
                url=url,
                source='reputation.su',
            ))

        return cases

    def _search_sudebnye_resheniya(self, company_name: str) -> List[CompanyCourtCase]:
        """
        Two-step session search on судебныерешения.рф.

        Identical flow to the person court search, just using the
        company name in the person_info field (the site searches both).
        """
        results: List[CompanyCourtCase] = []
        try:
            sess = requests.Session()
            sess.headers.update(_HEADERS)

            r = sess.get(self._SR_BASE + '/', timeout=self._sr_timeout)
            if r.status_code != 200:
                return results

            # CSRF token — name attr before or after value attr
            token_m = re.search(
                r'<input[^>]+name="simpleSearch\[_token\]"[^>]+value="([^"]+)"', r.text
            ) or re.search(
                r'<input[^>]+value="([^"]+)"[^>]+name="simpleSearch\[_token\]"', r.text
            )
            if not token_m:
                logger.debug("судебныерешения.рф: CSRF token not found")
                return results

            token = token_m.group(1)

            form = {
                'simpleSearch[person_info][0][person]': company_name,
                'simpleSearch[person_info][0][person_status]': '',
                'simpleSearch[content]': '',
                'simpleSearch[case_number]': '',
                'simpleSearch[case_vid]': '',
                'simpleSearch[case_stage]': '',
                'simpleSearch[_token]': token,
                'simpleSearch[search]': '',
            }

            r = sess.post(
                self._SR_BASE + '/simple_filter',
                data=form,
                timeout=self._sr_timeout,
                allow_redirects=True,
            )
            if r.status_code != 200:
                return results

            soup = BeautifulSoup(r.text, 'lxml')
            list_div = soup.select_one('#list')
            if not list_div:
                return results

            for table in list_div.select('table.table-bordered')[:25]:
                try:
                    rows = table.select('tr')
                    if len(rows) < 2:
                        continue

                    row1, row2 = rows[0], rows[1]
                    tds1 = row1.select('td')
                    if len(tds1) < 2:
                        continue

                    court_name = tds1[0].get_text(strip=True)
                    link = tds1[1].select_one('a')
                    if not link:
                        continue

                    raw_text = link.get_text(strip=True)
                    href = link.get('href', '')
                    url = (self._SR_BASE + href) if href.startswith('/') else href

                    m = re.search(r'(\d{1,2}[А-Яа-я]{0,3}-\d+/\d{4})', raw_text)
                    case_number = m.group(1) if m else raw_text

                    date = ''
                    role = ''
                    tds2 = row2.select('td')
                    if tds2:
                        dm = re.search(r'(\d{2}\.\d{2}\.\d{4})', tds2[0].get_text(strip=True))
                        if dm:
                            date = dm.group(1)
                    if len(tds2) > 1:
                        role = self._role_from_text(tds2[1].get_text(), company_name)

                    results.append(CompanyCourtCase(
                        case_number=case_number,
                        court_name=court_name,
                        case_type=self._normalize_case_type(raw_text + ' ' + court_name),
                        date=date,
                        role=role,
                        url=url,
                        source='судебныерешения.рф',
                    ))
                except Exception as exc:
                    logger.debug("судебныерешения.рф parse row error: %s", exc)

        except Exception as exc:
            logger.warning("судебныерешения.рф company search error: %s", exc)

        return results

    # ── Helpers ─────────────────────────────────────────────────────────────


    def _detect_company_role(self, card, company_name: str, inn: str) -> str:
        """Detect company's role from a reputation.su card participant lists."""
        name_lower = company_name.lower()
        identifiers = [name_lower]
        if inn:
            identifiers.append(inn)

        role_map = {
            'Истцы': 'истец',
            'Заявители': 'истец',
            'Взыскатели': 'истец',
            'Ответчики': 'ответчик',
            'Должники': 'должник',
            'Другие участники': 'третье лицо',
        }

        for li in card.select('li'):
            span = li.select_one('span')
            if not span:
                continue
            span_text = span.get_text(strip=True)
            for label, role in role_map.items():
                if label in span_text:
                    li_text = li.get_text(' ', strip=True).lower()
                    if any(ident in li_text for ident in identifiers):
                        return role

        return ''

    def _role_from_text(self, text: str, company_name: str) -> str:
        """Detect role from судебныерешения row text."""
        tl = text.lower()
        pos = tl.find(company_name.lower())
        if pos != -1:
            window = tl[max(0, pos - 100): pos + len(company_name) + 100]
            if any(kw in window for kw in _PLAINTIFF_KW):
                return 'истец'
            if 'должник' in window:
                return 'должник'
            if any(kw in window for kw in _DEFENDANT_KW):
                return 'ответчик'
        return ''

    @staticmethod
    def _normalize_case_type(text: str) -> str:
        tl = text.lower()
        if 'банкрот' in tl:
            return 'банкротное'
        if 'уголовн' in tl:
            return 'уголовное'
        if 'административн' in tl:
            return 'административное'
        if 'арбитраж' in tl:
            return 'арбитражное'
        return 'гражданское'
