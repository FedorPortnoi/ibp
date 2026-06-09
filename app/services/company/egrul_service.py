"""
EGRUL/EGRIP Company Profile Service
=====================================
Given a company INN (10-digit) or OGRN (13-digit), returns full profile:
  - Core registration data
  - Current and historical directors
  - Founders / shareholders

Sources (in priority order):
  1. egrul.org     — free JSON API, same FNS XML source as Контур.Фокус (100 req/day)
  2. egrul.nalog.ru — official FNS search (basic data + current director only)
  3. rusprofile.ru  — scraping fallback for partial enrichment
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/html, */*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}


# ─────────────────────────────────────────
# Data models
# ─────────────────────────────────────────

@dataclass
class Director:
    name: str
    inn: str = ""
    role: str = "Директор"
    date_from: str = ""
    is_current: bool = True

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'inn': self.inn,
            'role': self.role,
            'date_from': self.date_from,
            'is_current': self.is_current,
        }


@dataclass
class Founder:
    name: str
    inn: str = ""
    founder_type: str = "physical"   # "physical" or "legal"
    share_percent: str = ""
    share_amount: str = ""
    is_current: bool = True

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'inn': self.inn,
            'founder_type': self.founder_type,
            'share_percent': self.share_percent,
            'share_amount': self.share_amount,
            'is_current': self.is_current,
        }


@dataclass
class CompanyProfile:
    inn: str
    ogrn: str
    name: str
    short_name: str = ""
    company_type: str = ""
    status: str = ""
    registration_date: str = ""
    liquidation_date: str = ""
    kpp: str = ""
    address: str = ""
    region: str = ""
    capital: str = ""
    okved: str = ""
    okved_name: str = ""
    okved_additional: List[str] = field(default_factory=list)
    directors: List[Director] = field(default_factory=list)
    founders: List[Founder] = field(default_factory=list)
    employee_count: str = ""
    registration_authority: str = ""
    branches_count: int = 0
    source: str = ""
    url: str = ""

    def to_dict(self) -> Dict:
        return {
            'inn': self.inn,
            'ogrn': self.ogrn,
            'name': self.name,
            'short_name': self.short_name,
            'company_type': self.company_type,
            'status': self.status,
            'registration_date': self.registration_date,
            'liquidation_date': self.liquidation_date,
            'kpp': self.kpp,
            'address': self.address,
            'region': self.region,
            'capital': self.capital,
            'okved': self.okved,
            'okved_name': self.okved_name,
            'okved_additional': self.okved_additional,
            'directors': [d.to_dict() for d in self.directors],
            'founders': [f.to_dict() for f in self.founders],
            'employee_count': self.employee_count,
            'registration_authority': self.registration_authority,
            'branches_count': self.branches_count,
            'source': self.source,
            'url': self.url,
        }


# ─────────────────────────────────────────
# Service
# ─────────────────────────────────────────

class EGRULService:
    """Look up a Russian legal entity or sole proprietor by INN or OGRN."""

    EGRUL_ORG_BASE  = "https://egrul.org"
    NALOG_BASE      = "https://egrul.nalog.ru"
    RUSPROFILE_BASE = "https://www.rusprofile.ru"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ─── Public entry point ───────────────

    def lookup(self, inn: str = "", ogrn: str = "") -> Optional[CompanyProfile]:
        """
        Main entry point. Pass INN or OGRN (or both).
        Returns CompanyProfile or None if nothing found.
        """
        query = (inn or ogrn).strip()
        if not query:
            return None

        logger.info("EGRUL lookup: query=%s", query)

        # 1. egrul.org — primary, same FNS source as Контур.Фокус
        profile = self._lookup_egrul_org(query)

        # 2. nalog.ru fallback if egrul.org is down or returns nothing
        if not profile:
            logger.info("egrul.org missed — falling back to nalog.ru")
            profile = self._lookup_nalog(query)

        # 3. rusprofile enrichment — fill gaps in directors/founders if needed
        if profile and (not profile.directors or not profile.founders):
            self._enrich_rusprofile(profile)

        if profile:
            logger.info(
                "EGRUL lookup done: %s | directors=%d founders=%d source=%s",
                profile.name, len(profile.directors), len(profile.founders), profile.source,
            )

        return profile

    # ─────────────────────────────────────────
    # Source 1: egrul.org  (primary)
    # ─────────────────────────────────────────

    def _lookup_egrul_org(self, query: str) -> Optional[CompanyProfile]:
        """
        GET https://egrul.org/{INN_or_OGRN}.json
        Returns the official FNS XML parsed into JSON — same data as Контур.Фокус.
        Free, 100 req/day.
        """
        url = f"{self.EGRUL_ORG_BASE}/{query}.json"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 404:
                logger.info("egrul.org: 404 for query=%s", query)
                return None
            if resp.status_code != 200:
                logger.warning("egrul.org: HTTP %s for query=%s", resp.status_code, query)
                return None

            data = resp.json()
            profile = self._parse_egrul_org_json(data)
            if profile:
                profile.source = "egrul.org"
                profile.url = url
            return profile

        except Exception as exc:
            logger.warning("egrul.org lookup failed: %s", exc)
            return None

    def _parse_egrul_org_json(self, data: dict) -> Optional[CompanyProfile]:
        """
        Parse egrul.org JSON response.

        The JSON mirrors the official FNS XML schema. XML attributes are
        stored under the '@attributes' key. Single child elements are dicts;
        multiple children of the same tag become lists.

        Top-level structure:
          СвЮЛ   — legal entity (UL)
          СвИП   — sole proprietor (IP / ИП)
        """
        # Determine entity type
        ul_data = data.get('СвЮЛ')
        ip_data = data.get('СвИП')
        root = ul_data or ip_data
        is_ip = ip_data is not None and ul_data is None

        if not root:
            # Some responses put everything at the root level
            root = data
            is_ip = 'ОГРНИП' in data.get('@attributes', {})

        attrs = root.get('@attributes', {}) if isinstance(root, dict) else {}

        inn  = attrs.get('ИНН', '')
        ogrn = attrs.get('ОГРН', attrs.get('ОГРНИП', ''))
        kpp  = attrs.get('КПП', '')

        if not inn and not ogrn:
            return None

        # ── Name ──
        if is_ip:
            ip_fio = attrs.get('ФИОПолн', '')
            full_name  = f"ИП {ip_fio}" if ip_fio else f"ИП (ИНН {inn})"
            short_name = full_name
        else:
            name_block = root.get('СвНаимЮЛ', {})
            name_attrs = _attrs(name_block)
            full_name  = name_attrs.get('НаимЮЛПолн', attrs.get('НаимЮЛСокр', ''))
            short_name = name_attrs.get('НаимЮЛСокр', full_name)

        company_type = _detect_company_type(short_name or full_name)

        # ── Status ──
        status_block = root.get('СвСтатус', {})
        status_attrs = _attrs(status_block)
        raw_status = status_attrs.get('НаимСтатусЮЛ', '')
        status = _normalize_status(raw_status)
        liquidation_date = ''
        if status == 'Ликвидировано':
            liq_block = root.get('СвПрекрЮЛ', {})
            liquidation_date = _attrs(liq_block).get('ДатаПрекрЮЛ', '')

        # ── Registration date ──
        reg_date = attrs.get('ДатаОГРН', attrs.get('ДатаОГРНИП', ''))

        # ── Capital ──
        cap_block = root.get('СвУстКап', {})
        cap_raw   = _attrs(cap_block).get('СумКап', '')
        capital   = f"{cap_raw} руб." if cap_raw else ''

        # ── Address ──
        addr_block = root.get('СвАдресЮЛ', root.get('СвМНЖ', {}))
        address, region = _parse_address(addr_block)

        # ── Registration authority ──
        reg_org_block = root.get('СвРегОрг', {})
        reg_auth = _attrs(reg_org_block).get('НаимНО', '')

        # ── OKVEDs ──
        okved_block = root.get('СвОКВЭД', {})
        okved, okved_name, okved_additional = _parse_okveds(okved_block)

        # ── Branches ──
        branches_block = root.get('СвПодразд', {})
        branches = _as_list(branches_block.get('СвФилиал', [])) if isinstance(branches_block, dict) else []
        branches_count = len(branches)

        # ── Directors ──
        directors = _parse_directors(root.get('СведДолжнФЛ'), is_current=(status == 'Действующее'))

        # ── Founders ──
        founders = _parse_founders(root.get('СвУчредит'))

        return CompanyProfile(
            inn=inn,
            ogrn=ogrn,
            name=full_name,
            short_name=short_name,
            company_type=company_type,
            status=status,
            registration_date=reg_date,
            liquidation_date=liquidation_date,
            kpp=kpp,
            address=address,
            region=region,
            capital=capital,
            okved=okved,
            okved_name=okved_name,
            okved_additional=okved_additional,
            directors=directors,
            founders=founders,
            registration_authority=reg_auth,
            branches_count=branches_count,
        )

    # ─────────────────────────────────────────
    # Source 2: egrul.nalog.ru  (fallback)
    # ─────────────────────────────────────────

    def _lookup_nalog(self, query: str) -> Optional[CompanyProfile]:
        """
        Official nalog.ru 2-step search.
        Returns basic data + current director only (no founders, no all OKVEDs).
        Used only when egrul.org is unreachable.
        """
        try:
            resp = self.session.post(
                f"{self.NALOG_BASE}/",
                data={'query': query},
                headers={
                    **HEADERS,
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Origin': self.NALOG_BASE,
                    'Referer': f"{self.NALOG_BASE}/",
                    'X-Requested-With': 'XMLHttpRequest',
                },
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return None

            payload = resp.json()
            token = payload.get('t', '')
            if not token or payload.get('captchaRequired'):
                return None

        except Exception as exc:
            logger.warning("nalog.ru step 1: %s", exc)
            return None

        time.sleep(1.5)

        for attempt in range(3):
            try:
                resp2 = self.session.get(
                    f"{self.NALOG_BASE}/search-result/{token}",
                    headers={**HEADERS, 'Referer': f"{self.NALOG_BASE}/",
                             'X-Requested-With': 'XMLHttpRequest'},
                    timeout=self.timeout,
                )
                if resp2.status_code != 200:
                    time.sleep(1)
                    continue

                rows = resp2.json().get('rows', [])
                if not rows and attempt < 2:
                    time.sleep(2)
                    continue

                for row in rows:
                    profile = self._parse_nalog_row(row)
                    if profile:
                        return profile
                break

            except Exception as exc:
                logger.warning("nalog.ru step 2 attempt %d: %s", attempt + 1, exc)
                if attempt < 2:
                    time.sleep(1)

        return None

    def _parse_nalog_row(self, row: dict) -> Optional[CompanyProfile]:
        try:
            kind     = row.get('k', '')
            inn      = row.get('i', '')
            ogrn     = row.get('o', '')
            end_date = row.get('e', '')

            if not inn and not ogrn:
                return None

            if kind == 'fl':
                name = row.get('n', '')
                full_name = f"ИП {name}" if name and not name.upper().startswith('ИП') else name
                profile = CompanyProfile(
                    inn=inn, ogrn=ogrn,
                    name=full_name, short_name=full_name,
                    company_type='ИП',
                    status='Ликвидировано' if end_date else 'Действующее',
                    liquidation_date=end_date,
                    registration_date=row.get('r', ''),
                    address=row.get('a', '') or row.get('rn', ''),
                    kpp=row.get('p', ''),
                    source='egrul.nalog.ru',
                    url=f"{self.NALOG_BASE}/index.html",
                )
                profile.directors.append(Director(
                    name=name, role='ИП', is_current=not end_date,
                ))
                return profile

            short    = row.get('c', '') or row.get('n', '')
            full     = row.get('n', '') or short
            dir_raw  = row.get('g', '')

            profile = CompanyProfile(
                inn=inn, ogrn=ogrn,
                name=full, short_name=short,
                company_type=_detect_company_type(short or full),
                status='Ликвидировано' if end_date else 'Действующее',
                liquidation_date=end_date,
                registration_date=row.get('r', ''),
                address=row.get('a', '') or row.get('rn', ''),
                kpp=row.get('p', ''),
                source='egrul.nalog.ru (fallback)',
                url=f"{self.NALOG_BASE}/index.html",
            )
            if dir_raw:
                role, _, person = dir_raw.partition(':')
                person = person.strip() or dir_raw.strip()
                role   = role.strip().title() or 'Директор'
                if person:
                    profile.directors.append(Director(
                        name=person, role=role, is_current=not end_date,
                    ))
            return profile

        except Exception as exc:
            logger.debug("nalog.ru row parse: %s", exc)
            return None

    # ─────────────────────────────────────────
    # Source 3: rusprofile.ru  (enrichment)
    # ─────────────────────────────────────────

    def _enrich_rusprofile(self, profile: CompanyProfile) -> None:
        """
        Fill gaps — used only when egrul.org AND nalog.ru gave incomplete data.
        Tries OGRN page first, falls back to INN search.
        """
        ogrn = profile.ogrn
        is_ip = (profile.company_type == 'ИП' or (ogrn and len(ogrn) == 15))
        path = f"/ip/{ogrn}" if is_ip else f"/id/{ogrn}"

        try:
            url = f"{self.RUSPROFILE_BASE}{path}"
            resp = self.session.get(url, timeout=self.timeout)

            if resp.status_code == 404 and profile.inn:
                # Try by INN search
                search_resp = self.session.get(
                    f"{self.RUSPROFILE_BASE}/search?query={profile.inn}",
                    timeout=self.timeout,
                )
                if search_resp.status_code == 200:
                    soup = BeautifulSoup(search_resp.text, 'lxml')
                    link = soup.select_one('a.company-item__title, a.list-element__title')
                    if link and link.get('href'):
                        url = f"{self.RUSPROFILE_BASE}{link['href']}"
                        time.sleep(0.4)
                        resp = self.session.get(url, timeout=self.timeout)

            if resp.status_code in (403, 429, 404):
                return
            if resp.status_code != 200:
                return

            profile.url = profile.url or url
            self._parse_rusprofile_page(BeautifulSoup(resp.text, 'lxml'), profile)

        except Exception as exc:
            logger.warning("rusprofile enrich: %s", exc)

    def _parse_rusprofile_page(self, soup: BeautifulSoup, profile: CompanyProfile) -> None:
        text = soup.get_text()

        # Fill basic gaps
        if not profile.address:
            el = soup.select_one('.company-info__address, [itemprop="address"]')
            if el:
                profile.address = el.get_text(strip=True)

        if not profile.capital:
            m = re.search(r'(?:Уставный капитал|УК)[:\s]*([\d\s,.]+(?:руб|₽)?)', text, re.I)
            if m:
                profile.capital = m.group(1).strip()

        # Directors
        dir_section = soup.select_one('#directors, .company-directors')
        if dir_section:
            for entry in dir_section.select('tr, li, .person-item')[:20]:
                entry_text = entry.get_text(separator=' ', strip=True)
                name_m = re.search(
                    r'([А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?\s+'
                    r'[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)', entry_text,
                )
                if not name_m:
                    continue
                person = name_m.group(1).strip()
                role_m = re.search(
                    r'(Генеральный директор|Директор|Президент|Председатель|Управляющий)',
                    entry_text, re.I,
                )
                role = role_m.group(1) if role_m else 'Директор'
                if not any(d.name == person for d in profile.directors):
                    profile.directors.append(Director(
                        name=person, role=role, is_current=True,
                    ))

        # Founders
        found_section = soup.select_one('#founders, .company-founders')
        if found_section:
            for entry in found_section.select('tr, li, .person-item')[:30]:
                entry_text = entry.get_text(separator=' ', strip=True)
                name_m = re.search(
                    r'([А-ЯЁ«"][А-ЯЁа-яёa-zA-Z\s"«»\-]{3,60})', entry_text,
                )
                if not name_m:
                    continue
                founder_name = name_m.group(1).strip().rstrip('"»')
                share_m  = re.search(r'([\d,.]+)\s*%', entry_text)
                amount_m = re.search(r'([\d\s]+(?:руб|₽))', entry_text, re.I)
                inn_m    = re.search(r'ИНН[:\s]*(\d{10,12})', entry_text)
                ftype = (
                    'legal'
                    if any(t in founder_name.upper() for t in ('ООО', 'АО', 'ПАО', 'ЗАО', 'ОАО', 'НКО'))
                    else 'physical'
                )
                if not any(f.name == founder_name for f in profile.founders):
                    profile.founders.append(Founder(
                        name=founder_name,
                        inn=inn_m.group(1) if inn_m else '',
                        founder_type=ftype,
                        share_percent=share_m.group(1) if share_m else '',
                        share_amount=amount_m.group(1).strip() if amount_m else '',
                        is_current=True,
                    ))


# ─────────────────────────────────────────
# FNS JSON parsing helpers
# (egrul.org mirrors the official FNS XML schema)
# ─────────────────────────────────────────

def _attrs(node: Any) -> dict:
    """Safely get the @attributes dict from an FNS JSON node."""
    if isinstance(node, dict):
        return node.get('@attributes', {})
    return {}


def _as_list(val: Any) -> list:
    """FNS JSON: single child → dict, multiple children → list. Normalise."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        return [val]
    return []


def _fio(node: Any) -> str:
    """Build full name from СвФЛ node containing Фамилия / Имя / Отчество."""
    a = _attrs(node)
    parts = [a.get('Фамилия', ''), a.get('Имя', ''), a.get('Отчество', '')]
    return ' '.join(p for p in parts if p).strip()


def _parse_address(addr_block: Any) -> tuple:
    """Return (address_str, region_str) from СвАдресЮЛ node."""
    if not isinstance(addr_block, dict):
        return '', ''

    rf = addr_block.get('АдресРФ', addr_block)
    a  = _attrs(rf)

    postal   = a.get('Индекс', '')
    region   = _attrs(rf.get('Регион', {})).get('НаимРегион', '')
    city_raw = rf.get('Город', rf.get('НаселПункт', {}))
    city     = _attrs(city_raw).get('НаимГород', _attrs(city_raw).get('НаимНаселПункт', ''))
    street_raw = rf.get('Улица', {})
    street   = _attrs(street_raw).get('НаимУлица', '')
    house    = a.get('Дом', '')
    building = a.get('Корпус', '')
    office   = a.get('Кварт', '')

    parts = []
    if postal:
        parts.append(postal)
    if region:
        parts.append(region)
    if city:
        parts.append(city)
    if street:
        parts.append(street)
    if house:
        parts.append(f"д. {house}")
    if building:
        parts.append(f"корп. {building}")
    if office:
        parts.append(f"оф. {office}")

    return ', '.join(parts), region


def _parse_okveds(okved_block: Any) -> tuple:
    """Return (primary_code, primary_name, [additional_code_strings])."""
    if not isinstance(okved_block, dict):
        return '', '', []

    primary_node = okved_block.get('СвОКВЭДОсн', {})
    pa = _attrs(primary_node)
    primary_code = pa.get('КодОКВЭД', '')
    primary_name = pa.get('НаимОКВЭД', '')

    additional = []
    for node in _as_list(okved_block.get('СвОКВЭДДоп')):
        a    = _attrs(node)
        code = a.get('КодОКВЭД', '')
        name = a.get('НаимОКВЭД', '')
        if code:
            additional.append(f"{code} — {name}" if name else code)

    return primary_code, primary_name, additional


def _parse_directors(raw: Any, is_current: bool = True) -> List[Director]:
    """
    Parse СведДолжнФЛ.
    Each entry has СвФЛ (name + INN) and СвДолжн (role).
    ОгрДосСв="1" means personal data is restricted — skip that entry.
    """
    result = []
    for entry in _as_list(raw):
        if not isinstance(entry, dict):
            continue
        # Skip restricted entries
        if _attrs(entry).get('ОгрДосСв') == '1':
            continue

        fl_node   = entry.get('СвФЛ', {})
        role_node = entry.get('СвДолжн', {})
        date_node = entry.get('ГРНДатаПерв', {})

        name = _fio(fl_node)
        if not name:
            continue

        inn_fl   = _attrs(fl_node).get('ИННФЛ', '')
        role_raw = _attrs(role_node).get('НаимДолжн', _attrs(role_node).get('НаимВидДолжн', 'Директор'))
        date_from = _attrs(date_node).get('ДатаЗаписи', '')

        # Check if this is a historical record (has dismissal date)
        end_node = entry.get('ГРНДатаИспр', entry.get('СвПрекрПолн', {}))
        end_date = _attrs(end_node).get('ДатаЗаписи', '')
        current  = is_current and not end_date

        result.append(Director(
            name=name,
            inn=inn_fl,
            role=role_raw.strip().capitalize() if role_raw else 'Директор',
            date_from=date_from,
            is_current=current,
        ))

    return result


def _parse_founders(raw: Any) -> List[Founder]:
    """
    Parse СвУчредит containing:
      УчрФЛ      — physical person founders
      УчрЮЛРос   — Russian legal entity founders
      УчрЮЛИн    — Foreign legal entity founders (rare)
    """
    if not isinstance(raw, dict):
        return []

    result = []

    # Physical person founders
    for entry in _as_list(raw.get('УчрФЛ')):
        if not isinstance(entry, dict):
            continue
        if _attrs(entry).get('ОгрДосСв') == '1':
            continue

        fl_node    = entry.get('СвФЛ', {})
        share_node = entry.get('ДолУстКап', {})
        date_node  = entry.get('ГРНДатаПерв', {})

        name = _fio(fl_node)
        if not name:
            continue

        inn_fl    = _attrs(fl_node).get('ИННФЛ', '')
        share_pct = _attrs(share_node).get('Процент', '')
        share_amt = _attrs(share_node).get('НоминСтоим', '')
        if share_amt:
            share_amt = f"{share_amt} руб."

        end_node = entry.get('СвВыход', {})
        is_current = not bool(_attrs(end_node).get('ДатаВыход', ''))

        result.append(Founder(
            name=name,
            inn=inn_fl,
            founder_type='physical',
            share_percent=share_pct,
            share_amount=share_amt,
            is_current=is_current,
        ))

    # Russian legal entity founders
    for entry in _as_list(raw.get('УчрЮЛРос')):
        if not isinstance(entry, dict):
            continue

        name_node  = entry.get('НаимИННЮЛ', {})
        share_node = entry.get('ДолУстКап', {})

        na = _attrs(name_node)
        name = na.get('НаимЮЛПолн', na.get('НаимЮЛСокр', ''))
        if not name:
            continue

        inn_ul    = na.get('ИНН', '')
        share_pct = _attrs(share_node).get('Процент', '')
        share_amt = _attrs(share_node).get('НоминСтоим', '')
        if share_amt:
            share_amt = f"{share_amt} руб."

        end_node   = entry.get('СвВыход', {})
        is_current = not bool(_attrs(end_node).get('ДатаВыход', ''))

        result.append(Founder(
            name=name,
            inn=inn_ul,
            founder_type='legal',
            share_percent=share_pct,
            share_amount=share_amt,
            is_current=is_current,
        ))

    # Foreign legal entity founders
    for entry in _as_list(raw.get('УчрЮЛИн')):
        if not isinstance(entry, dict):
            continue
        name_node  = entry.get('СвНаимЮЛ', {})
        share_node = entry.get('ДолУстКап', {})
        name = _attrs(name_node).get('НаимЮЛПолн', '')
        if not name:
            continue
        share_pct = _attrs(share_node).get('Процент', '')
        share_amt = _attrs(share_node).get('НоминСтоим', '')
        if share_amt:
            share_amt = f"{share_amt} руб."
        result.append(Founder(
            name=name,
            founder_type='legal',
            share_percent=share_pct,
            share_amount=share_amt,
            is_current=True,
        ))

    return result


def _normalize_status(raw: str) -> str:
    if not raw:
        return 'Действующее'
    raw_lower = raw.lower()
    if 'ликвидир' in raw_lower:
        return 'Ликвидировано'
    if 'реорганизац' in raw_lower:
        return 'В стадии реорганизации'
    if 'ликвидац' in raw_lower:
        return 'В стадии ликвидации'
    if 'недостовер' in raw_lower:
        return 'Недостоверные сведения'
    return 'Действующее'


def _detect_company_type(name: str) -> str:
    n = name.upper()
    for t in ('ПАО', 'ОАО', 'ЗАО', 'АО', 'ООО', 'НКО', 'ГУП', 'МУП', 'ИП'):
        if t in n:
            return t
    return ''


# ─────────────────────────────────────────
# Validation helpers
# ─────────────────────────────────────────

def validate_inn(inn: str) -> tuple:
    """
    Validate Russian INN format.
    Returns (is_valid: bool, entity_type: str)
    entity_type: 'company' (10 digits) | 'individual' (12 digits) | 'unknown'
    """
    if not inn or not inn.isdigit():
        return False, 'unknown'
    if len(inn) == 10:
        return True, 'company'
    if len(inn) == 12:
        return True, 'individual'
    return False, 'unknown'


def validate_ogrn(ogrn: str) -> tuple:
    """
    Validate Russian OGRN format.
    Returns (is_valid: bool, entity_type: str)
    entity_type: 'company' (13 digits) | 'individual_ip' (15 digits) | 'unknown'
    """
    if not ogrn or not ogrn.isdigit():
        return False, 'unknown'
    if len(ogrn) == 13:
        return True, 'company'
    if len(ogrn) == 15:
        return True, 'individual_ip'
    return False, 'unknown'
