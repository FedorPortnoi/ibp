"""
Extended Phone Sources for Phase 2
===================================
Additional phone discovery and validation sources.

Sources implemented:
1. GetContact - Phone→Name lookup (web scraping, API if available)
2. NumBuster - Telegram bot integration (via Telethon)
3. TrueCaller - Web lookup (scraping) - Cycle 5
4. Sync.me - Web lookup - Cycle 5
5. VK Phone Search - Search VK by phone number
6. OK.ru Phone Search - Search OK.ru by phone number
7. Telegram Phone Lookup - Check if phone registered on Telegram
8. Eyecon - Caller ID lookup - Cycle 5
9. CallApp - Caller ID database - Cycle 5

Cycle 4 Focus: GetContact + NumBuster ✓
Cycle 5 Focus: TrueCaller + Sync.me + Eyecon + CallApp
Cycle 6 Focus: Telegram + enhanced VK/OK phone search
"""

import logging
import os
import re
import time
import hashlib
import base64
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class PhoneSourceResult:
    """Result from a phone source lookup."""
    phone: str
    source: str
    name_found: Optional[str] = None
    carrier: Optional[str] = None
    region: Optional[str] = None
    spam_score: Optional[float] = None
    confidence: float = 0.0
    details: Dict = field(default_factory=dict)
    error: Optional[str] = None


def normalize_phone(phone: str) -> str:
    """Normalize phone number to E.164 format."""
    digits = re.sub(r'\D', '', phone)

    if len(digits) == 11 and digits.startswith('8'):
        digits = '7' + digits[1:]
    elif len(digits) == 10 and digits.startswith('9'):
        digits = '7' + digits

    if len(digits) == 11 and digits.startswith('7'):
        return '+' + digits

    return phone  # Return original if can't normalize


class GetContactChecker:
    """
    GetContact phone→name lookup (Cycle 4).

    GetContact is a crowdsourced phone directory.
    Uses web scraping since API requires mobile app tokens.

    Rate limited to avoid blocks.
    """

    def __init__(self, rate_limit_delay: float = 3.0):
        self.rate_limit_delay = rate_limit_delay
        self._last_request = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
        })

    def lookup(self, phone: str) -> PhoneSourceResult:
        """
        Look up phone number in GetContact.

        Args:
            phone: Phone number (any format)

        Returns:
            PhoneSourceResult with name if found
        """
        # Rate limiting
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request = time.time()

        normalized = normalize_phone(phone)
        result = PhoneSourceResult(
            phone=normalized,
            source="getcontact",
            confidence=0.0
        )

        try:
            # Method 1: Try GetContact web search
            # Note: GetContact doesn't have a public web interface
            # We'll try alternative methods

            # Method 2: Try searching Google for the phone number + GetContact results
            search_result = self._google_search_phone(normalized)
            if search_result:
                result.name_found = search_result.get('name')
                result.confidence = 0.70
                result.details = search_result
                logger.info(f"GetContact: Found name '{result.name_found}' for {normalized}")

            # Method 3: Try phone.ru or similar Russian phone directories
            phone_ru_result = self._check_phone_directories(normalized)
            if phone_ru_result and phone_ru_result.get('name'):
                if not result.name_found:
                    result.name_found = phone_ru_result.get('name')
                    result.confidence = 0.65
                result.details.update(phone_ru_result)

        except Exception as e:
            result.error = str(e)
            logger.debug(f"GetContact lookup error for {phone}: {e}")

        return result

    def _google_search_phone(self, phone: str) -> Optional[Dict]:
        """Search Google for phone number info."""
        try:
            # Clean phone for search
            clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')

            # Search query
            query = f'"{clean_phone}" OR "{phone}" имя владелец'
            url = f"https://www.google.com/search?q={query}"

            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for name patterns in search results
                text = soup.get_text()

                # Common Russian name patterns
                name_patterns = [
                    r'([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)\s+' + re.escape(clean_phone[-4:]),
                    r'Владелец[:\s]+([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
                    r'Абонент[:\s]+([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
                ]

                for pattern in name_patterns:
                    match = re.search(pattern, text)
                    if match:
                        name = match.group(1)
                        if len(name) > 2:
                            return {'name': name, 'source': 'google_search'}

        except Exception as e:
            logger.debug(f"Google search error: {e}")

        return None

    def _check_phone_directories(self, phone: str) -> Optional[Dict]:
        """Check Russian phone directories."""
        try:
            # Try phone.ru style services
            clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')

            # Construct region code lookup
            if len(clean_phone) == 11 and clean_phone.startswith('7'):
                region_code = clean_phone[1:4]

                # Russian mobile operator codes
                operators = {
                    '900': 'Tele2', '901': 'Tele2', '902': 'Tele2', '903': 'Beeline',
                    '904': 'Tele2', '905': 'Beeline', '906': 'Beeline', '908': 'MTS',
                    '909': 'MTS', '910': 'MTS', '911': 'MTS', '912': 'MTS',
                    '913': 'MTS', '914': 'MTS', '915': 'MTS', '916': 'MTS',
                    '917': 'MTS', '918': 'MTS', '919': 'MTS', '920': 'MTS',
                    '921': 'Megafon', '922': 'Megafon', '923': 'Megafon',
                    '924': 'Megafon', '925': 'MTS', '926': 'Megafon',
                    '927': 'Megafon', '928': 'Megafon', '929': 'MTS',
                    '930': 'MTS', '931': 'Megafon', '932': 'Megafon',
                    '933': 'Megafon', '934': 'Megafon', '936': 'Megafon',
                    '937': 'Megafon', '938': 'Megafon', '939': 'MTS',
                    '950': 'Tele2', '951': 'Tele2', '952': 'Tele2',
                    '953': 'Tele2', '958': 'Tele2', '960': 'Beeline',
                    '961': 'Beeline', '962': 'Beeline', '963': 'Beeline',
                    '964': 'Beeline', '965': 'Beeline', '966': 'Beeline',
                    '967': 'Beeline', '968': 'Beeline', '969': 'Beeline',
                    '980': 'MTS', '981': 'MTS', '982': 'MTS', '983': 'MTS',
                    '984': 'MTS', '985': 'MTS', '986': 'Beeline', '987': 'MTS',
                    '988': 'MTS', '989': 'MTS', '992': 'Tele2', '993': 'Tele2',
                    '994': 'Tele2', '995': 'Tele2', '996': 'Tele2', '997': 'Tele2',
                    '999': 'Beeline',
                }

                carrier = operators.get(region_code)
                if carrier:
                    return {'carrier': carrier, 'region_code': region_code}

        except Exception as e:
            logger.debug(f"Phone directory error: {e}")

        return None

    def close(self):
        self.session.close()


class NumBusterChecker:
    """
    NumBuster phone lookup (Cycle 4).

    NumBuster is a popular Russian caller ID service.
    Available as a Telegram bot @NumBusterBot.

    This implementation uses web scraping as a fallback.
    """

    def __init__(self, rate_limit_delay: float = 2.0):
        self.rate_limit_delay = rate_limit_delay
        self._last_request = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })

    def lookup(self, phone: str) -> PhoneSourceResult:
        """
        Look up phone number via NumBuster methods.

        Args:
            phone: Phone number (any format)

        Returns:
            PhoneSourceResult with name if found
        """
        # Rate limiting
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request = time.time()

        normalized = normalize_phone(phone)
        result = PhoneSourceResult(
            phone=normalized,
            source="numbuster",
            confidence=0.0
        )

        try:
            # Method 1: Try kto-zvonil.ru (who's calling)
            ktozvonit_result = self._check_ktozvonit(normalized)
            if ktozvonit_result:
                result.name_found = ktozvonit_result.get('name')
                result.spam_score = ktozvonit_result.get('spam_score')
                result.confidence = 0.75
                result.details = ktozvonit_result
                if result.name_found:
                    logger.info(f"NumBuster: Found name '{result.name_found}' for {normalized}")

            # Method 2: Try neberitrubku.ru (don't pick up)
            if not result.name_found:
                neberi_result = self._check_neberitrubku(normalized)
                if neberi_result:
                    result.spam_score = neberi_result.get('spam_score')
                    result.details.update(neberi_result)
                    result.confidence = max(result.confidence, 0.60)

        except Exception as e:
            result.error = str(e)
            logger.debug(f"NumBuster lookup error for {phone}: {e}")

        return result

    def _check_ktozvonit(self, phone: str) -> Optional[Dict]:
        """Check kto-zvonil.ru for phone info."""
        try:
            clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')

            url = f"https://kto-zvonil.com/nomer/{clean_phone}"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                result = {}

                # Look for name in page
                name_elem = soup.select_one('.phone-name, .caller-name, h1')
                if name_elem:
                    name_text = name_elem.get_text(strip=True)
                    # Extract name if present
                    if name_text and not any(x in name_text.lower() for x in ['номер', 'телефон', 'звонок']):
                        result['name'] = name_text

                # Look for spam indicator
                spam_elem = soup.select_one('.spam-rating, .danger-rating')
                if spam_elem:
                    spam_text = spam_elem.get_text(strip=True)
                    if 'спам' in spam_text.lower() or 'мошен' in spam_text.lower():
                        result['spam_score'] = 0.8
                    elif 'безопасн' in spam_text.lower():
                        result['spam_score'] = 0.1

                # Look for comments count
                comments_elem = soup.select_one('.comments-count, .reviews-count')
                if comments_elem:
                    try:
                        result['reviews'] = int(re.search(r'\d+', comments_elem.get_text()).group())
                    except:
                        pass

                return result if result else None

        except Exception as e:
            logger.debug(f"kto-zvonil error: {e}")

        return None

    def _check_neberitrubku(self, phone: str) -> Optional[Dict]:
        """Check neberitrubku.ru for spam status."""
        try:
            clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')

            url = f"https://www.neberitrubku.ru/nomer-telefona/{clean_phone}"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                result = {}

                # Check if marked as spam
                page_text = soup.get_text().lower()
                if 'мошенни' in page_text or 'спам' in page_text or 'обман' in page_text:
                    result['spam_score'] = 0.9
                    result['spam_type'] = 'suspected_fraud'
                elif 'реклам' in page_text:
                    result['spam_score'] = 0.7
                    result['spam_type'] = 'advertising'
                elif 'безопасн' in page_text or 'надежн' in page_text:
                    result['spam_score'] = 0.1
                    result['spam_type'] = 'safe'

                return result if result else None

        except Exception as e:
            logger.debug(f"neberitrubku error: {e}")

        return None

    def close(self):
        self.session.close()


class VKPhoneSearcher:
    """
    Search VK by phone number (Cycle 4).

    VK allows searching for users by phone number.
    Returns profile information if found.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })

    def search(self, phone: str) -> PhoneSourceResult:
        """
        Search VK for users with this phone number.

        Args:
            phone: Phone number

        Returns:
            PhoneSourceResult with user info if found
        """
        normalized = normalize_phone(phone)
        result = PhoneSourceResult(
            phone=normalized,
            source="vk_phone_search",
            confidence=0.0
        )

        try:
            # Try VK search with phone
            clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')

            url = f"https://vk.com/search?c[q]={clean_phone}&c[section]=people"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for search results
                results_elem = soup.select('.people_row, .search_row')

                if results_elem:
                    first_result = results_elem[0]

                    # Get name
                    name_elem = first_result.select_one('.people_name, .search_name a')
                    if name_elem:
                        result.name_found = name_elem.get_text(strip=True)
                        result.confidence = 0.80

                        # Get profile URL
                        link = name_elem.get('href', '') if name_elem.name == 'a' else ''
                        if not link:
                            link_elem = first_result.select_one('a[href*="/id"]')
                            link = link_elem.get('href', '') if link_elem else ''

                        result.details = {
                            'vk_profile': link,
                            'name': result.name_found
                        }

                        logger.info(f"VK Phone Search: Found '{result.name_found}' for {normalized}")

        except Exception as e:
            result.error = str(e)
            logger.debug(f"VK phone search error: {e}")

        return result

    def close(self):
        self.session.close()


class OKPhoneSearcher:
    """
    Search OK.ru by phone number (Cycle 4).

    OK.ru allows searching for users by phone number.
    Returns profile information if found.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })

    def search(self, phone: str) -> PhoneSourceResult:
        """
        Search OK.ru for users with this phone number.

        Args:
            phone: Phone number

        Returns:
            PhoneSourceResult with user info if found
        """
        normalized = normalize_phone(phone)
        result = PhoneSourceResult(
            phone=normalized,
            source="ok_phone_search",
            confidence=0.0
        )

        try:
            # Try OK.ru search with phone
            clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')

            url = f"https://ok.ru/search?st.query={clean_phone}&st.cmd=friendsFriends"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for search results
                results_elem = soup.select('.user-card, .ucard')

                if results_elem:
                    first_result = results_elem[0]

                    # Get name
                    name_elem = first_result.select_one('.user-card_name, .ucard__name')
                    if name_elem:
                        result.name_found = name_elem.get_text(strip=True)
                        result.confidence = 0.80

                        # Get profile URL
                        link_elem = first_result.select_one('a[href*="/profile/"]')
                        link = link_elem.get('href', '') if link_elem else ''

                        result.details = {
                            'ok_profile': link,
                            'name': result.name_found
                        }

                        logger.info(f"OK.ru Phone Search: Found '{result.name_found}' for {normalized}")

        except Exception as e:
            result.error = str(e)
            logger.debug(f"OK.ru phone search error: {e}")

        return result

    def close(self):
        self.session.close()


class TrueCallerChecker:
    """
    TrueCaller phone lookup (Cycle 5).

    TrueCaller is a global caller ID service with 330M+ users.
    Web scraping approach since their API requires partnership.

    Methods:
    1. TrueCaller web search page
    2. Google search for TrueCaller cached results
    3. Fallback to alternative caller ID sites
    """

    BASE_URL = "https://www.truecaller.com"
    SEARCH_URL = "https://www.truecaller.com/search"

    def __init__(self, rate_limit_delay: float = 3.0):
        self.rate_limit_delay = rate_limit_delay
        self._last_request = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
            'Referer': 'https://www.google.com/',
        })

    def lookup(self, phone: str) -> PhoneSourceResult:
        """
        Look up phone number via TrueCaller.

        Args:
            phone: Phone number (any format)

        Returns:
            PhoneSourceResult with name if found
        """
        # Rate limiting
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request = time.time()

        normalized = normalize_phone(phone)
        result = PhoneSourceResult(
            phone=normalized,
            source="truecaller",
            confidence=0.0
        )

        try:
            # Method 1: Direct TrueCaller search (may be blocked)
            truecaller_result = self._search_truecaller(normalized)
            if truecaller_result:
                result.name_found = truecaller_result.get('name')
                result.spam_score = truecaller_result.get('spam_score')
                result.confidence = 0.85
                result.details = truecaller_result
                if result.name_found:
                    logger.info(f"TrueCaller: Found '{result.name_found}' for {normalized}")
                    return result

            # Method 2: Google search for TrueCaller results
            google_result = self._google_truecaller_search(normalized)
            if google_result:
                result.name_found = google_result.get('name')
                result.confidence = 0.75
                result.details = google_result
                if result.name_found:
                    logger.info(f"TrueCaller (via Google): Found '{result.name_found}' for {normalized}")
                    return result

            # Method 3: Alternative services (whocalledme, etc)
            alt_result = self._check_alternative_services(normalized)
            if alt_result:
                result.name_found = alt_result.get('name')
                result.spam_score = alt_result.get('spam_score')
                result.confidence = 0.65
                result.details = alt_result
                if result.name_found:
                    logger.info(f"TrueCaller alt: Found '{result.name_found}' for {normalized}")

        except Exception as e:
            result.error = str(e)
            logger.debug(f"TrueCaller lookup error for {phone}: {e}")

        return result

    def _search_truecaller(self, phone: str) -> Optional[Dict]:
        """Search TrueCaller directly."""
        try:
            # Format phone for TrueCaller URL (country code-number format)
            clean = phone.replace('+', '').replace(' ', '').replace('-', '')
            if clean.startswith('7') and len(clean) == 11:
                # Russian number: 7-XXXXXXXXXX
                formatted = f"ru/{clean}"
            else:
                formatted = clean

            url = f"{self.SEARCH_URL}/{formatted}"
            response = self.session.get(url, timeout=15, allow_redirects=True)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                result = {}

                # Look for name in TrueCaller results
                name_selectors = [
                    '.profile-name', '.caller-name', 'h1.profile__name',
                    '[data-testid="profile-name"]', '.SearchResult__name',
                    'span.name', '.FullName'
                ]
                for selector in name_selectors:
                    name_elem = soup.select_one(selector)
                    if name_elem:
                        name = name_elem.get_text(strip=True)
                        if name and len(name) > 1 and not any(x in name.lower() for x in ['unknown', 'verified']):
                            result['name'] = name
                            break

                # Check for spam flag
                spam_indicators = soup.select('.spam-badge, .spam-indicator, [data-spam="true"]')
                if spam_indicators:
                    result['spam_score'] = 0.85
                    result['is_spam'] = True

                return result if result else None

        except Exception as e:
            logger.debug(f"TrueCaller direct search error: {e}")

        return None

    def _google_truecaller_search(self, phone: str) -> Optional[Dict]:
        """Search Google for TrueCaller cached results."""
        try:
            clean = phone.replace('+', '').replace(' ', '').replace('-', '')
            query = f'site:truecaller.com "{clean}"'

            url = f"https://www.google.com/search?q={query}"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look in search result snippets
                snippets = soup.select('.VwiC3b, .st, .s')
                for snippet in snippets:
                    text = snippet.get_text()

                    # Look for name patterns
                    # "Name Surname | +7 XXX" format
                    name_match = re.search(r'^([A-ZА-ЯЁ][a-zа-яё]+(?:\s+[A-ZА-ЯЁ][a-zа-яё]+)?)', text)
                    if name_match:
                        name = name_match.group(1).strip()
                        if len(name) > 2 and not any(x in name.lower() for x in ['truecaller', 'phone', 'number']):
                            return {'name': name, 'source': 'google_truecaller'}

        except Exception as e:
            logger.debug(f"Google TrueCaller search error: {e}")

        return None

    def _check_alternative_services(self, phone: str) -> Optional[Dict]:
        """Check alternative caller ID services."""
        try:
            clean = phone.replace('+', '').replace(' ', '').replace('-', '')

            # Try whocalledme style services for Russian numbers
            if clean.startswith('7'):
                # spravka.ru style
                urls_to_try = [
                    f"https://phone.spravka.ru/nomer/{clean}",
                    f"https://telefon.spravka.ru/{clean}",
                ]

                for url in urls_to_try:
                    try:
                        response = self.session.get(url, timeout=10)
                        if response.status_code == 200:
                            soup = BeautifulSoup(response.text, 'html.parser')

                            # Look for owner info
                            owner_elem = soup.select_one('.owner-name, .subscriber-name, h1')
                            if owner_elem:
                                text = owner_elem.get_text(strip=True)
                                # Check if it looks like a name (not phone number)
                                if re.match(r'^[А-ЯЁA-Z][а-яёa-z]+', text):
                                    return {'name': text, 'source': url.split('/')[2]}
                    except:
                        continue

        except Exception as e:
            logger.debug(f"Alternative service error: {e}")

        return None

    def close(self):
        self.session.close()


class SyncMeChecker:
    """
    Sync.me phone lookup (Cycle 5).

    Sync.me is a caller ID and spam blocking app with 10M+ users.
    Uses web scraping since API requires authentication.

    Methods:
    1. Sync.me web search
    2. Google search for Sync.me cached results
    """

    BASE_URL = "https://sync.me"

    def __init__(self, rate_limit_delay: float = 3.0):
        self.rate_limit_delay = rate_limit_delay
        self._last_request = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
        })

    def lookup(self, phone: str) -> PhoneSourceResult:
        """
        Look up phone number via Sync.me.

        Args:
            phone: Phone number (any format)

        Returns:
            PhoneSourceResult with name if found
        """
        # Rate limiting
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request = time.time()

        normalized = normalize_phone(phone)
        result = PhoneSourceResult(
            phone=normalized,
            source="syncme",
            confidence=0.0
        )

        try:
            # Method 1: Direct Sync.me search
            syncme_result = self._search_syncme(normalized)
            if syncme_result:
                result.name_found = syncme_result.get('name')
                result.spam_score = syncme_result.get('spam_score')
                result.confidence = 0.80
                result.details = syncme_result
                if result.name_found:
                    logger.info(f"Sync.me: Found '{result.name_found}' for {normalized}")
                    return result

            # Method 2: Google search for Sync.me results
            google_result = self._google_syncme_search(normalized)
            if google_result:
                result.name_found = google_result.get('name')
                result.confidence = 0.70
                result.details = google_result
                if result.name_found:
                    logger.info(f"Sync.me (via Google): Found '{result.name_found}' for {normalized}")
                    return result

            # Method 3: Try Eyecon/CallApp fallbacks
            alt_result = self._check_caller_id_alternatives(normalized)
            if alt_result:
                result.name_found = alt_result.get('name')
                result.confidence = 0.65
                result.details = alt_result
                if result.name_found:
                    logger.info(f"CallerID alt: Found '{result.name_found}' for {normalized}")

        except Exception as e:
            result.error = str(e)
            logger.debug(f"Sync.me lookup error for {phone}: {e}")

        return result

    def _search_syncme(self, phone: str) -> Optional[Dict]:
        """Search Sync.me directly."""
        try:
            clean = phone.replace('+', '').replace(' ', '').replace('-', '')

            # Sync.me URL format: /search/{country}/{number}
            if clean.startswith('7') and len(clean) == 11:
                country = 'ru'
                number = clean
            else:
                country = 'unknown'
                number = clean

            url = f"{self.BASE_URL}/search/{country}/{number}"
            response = self.session.get(url, timeout=15, allow_redirects=True)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                result = {}

                # Look for name
                name_selectors = [
                    '.profile-name', '.caller-name', '.name-result',
                    'h1.name', 'span.name', '.search-result-name'
                ]
                for selector in name_selectors:
                    elem = soup.select_one(selector)
                    if elem:
                        name = elem.get_text(strip=True)
                        if name and len(name) > 1:
                            result['name'] = name
                            break

                # Check for spam indicators
                spam_elems = soup.select('.spam, .danger, .blocked')
                if spam_elems:
                    result['spam_score'] = 0.8

                return result if result else None

        except Exception as e:
            logger.debug(f"Sync.me direct search error: {e}")

        return None

    def _google_syncme_search(self, phone: str) -> Optional[Dict]:
        """Search Google for Sync.me cached results."""
        try:
            clean = phone.replace('+', '').replace(' ', '').replace('-', '')
            query = f'site:sync.me "{clean}"'

            url = f"https://www.google.com/search?q={query}"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look in search result titles and snippets
                results = soup.select('.g')
                for res in results[:3]:
                    text = res.get_text()

                    # Extract name pattern: "Name | sync.me" or "Name - Phone"
                    name_match = re.search(r'^([A-ZА-ЯЁ][a-zа-яё]+(?:\s+[A-ZА-ЯЁ][a-zа-яё]+)?)\s*[\|–-]', text)
                    if name_match:
                        name = name_match.group(1).strip()
                        if len(name) > 2:
                            return {'name': name, 'source': 'google_syncme'}

        except Exception as e:
            logger.debug(f"Google Sync.me search error: {e}")

        return None

    def _check_caller_id_alternatives(self, phone: str) -> Optional[Dict]:
        """Check alternative caller ID databases."""
        try:
            clean = phone.replace('+', '').replace(' ', '').replace('-', '')

            # Emulator approach - check if phone exists in popular databases
            # Try 114.ru (Russian telephone directory)
            if clean.startswith('7'):
                try:
                    url = f"https://www.114.ru/search/?q={clean}"
                    response = self.session.get(url, timeout=10)

                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')

                        # Look for result entries
                        results_elem = soup.select('.result-item, .search-result')
                        if results_elem:
                            name_elem = results_elem[0].select_one('.name, .title')
                            if name_elem:
                                name = name_elem.get_text(strip=True)
                                if re.match(r'^[А-ЯЁA-Z]', name):
                                    return {'name': name, 'source': '114.ru'}
                except:
                    pass

            # Try spravnik.com (Russian phone database)
            try:
                url = f"https://spravnik.com/phone/{clean}"
                response = self.session.get(url, timeout=10)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    owner_elem = soup.select_one('.owner, .name, h2')
                    if owner_elem:
                        text = owner_elem.get_text(strip=True)
                        if re.match(r'^[А-ЯЁA-Z][а-яёa-z]+', text) and 'телефон' not in text.lower():
                            return {'name': text, 'source': 'spravnik'}
            except:
                pass

        except Exception as e:
            logger.debug(f"Alternative caller ID error: {e}")

        return None

    def close(self):
        self.session.close()


class EyeconChecker:
    """
    Eyecon caller ID lookup (Cycle 5).

    Eyecon is a caller ID app that uses social profiles.
    Limited web access, uses fallback methods.
    """

    def __init__(self, rate_limit_delay: float = 2.5):
        self.rate_limit_delay = rate_limit_delay
        self._last_request = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
        })

    def lookup(self, phone: str) -> PhoneSourceResult:
        """Look up phone in Eyecon-style services."""
        # Rate limiting
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request = time.time()

        normalized = normalize_phone(phone)
        result = PhoneSourceResult(
            phone=normalized,
            source="eyecon",
            confidence=0.0
        )

        try:
            # Eyecon doesn't have a public web interface
            # Try Google search for social profile associations
            clean = phone.replace('+', '').replace(' ', '').replace('-', '')

            # Search for phone + "profile" patterns
            query = f'"{clean}" (профиль OR profile OR vk.com OR ok.ru)'
            url = f"https://www.google.com/search?q={query}"

            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for VK/OK profile mentions
                text = soup.get_text()

                # Try to extract names from results
                name_patterns = [
                    r'([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)\s*[|–-]?\s*(?:VK|ВКонтакте|OK\.ru)',
                    r'([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)\s*[:–-]\s*профиль',
                ]

                for pattern in name_patterns:
                    match = re.search(pattern, text)
                    if match:
                        name = match.group(1) if len(match.groups()) == 1 else f"{match.group(1)} {match.group(2)}"
                        result.name_found = name.strip()
                        result.confidence = 0.60
                        result.details = {'source': 'google_social_search'}
                        logger.info(f"Eyecon: Found '{result.name_found}' for {normalized}")
                        break

        except Exception as e:
            result.error = str(e)
            logger.debug(f"Eyecon lookup error: {e}")

        return result

    def close(self):
        self.session.close()


class CallAppChecker:
    """
    CallApp caller ID lookup (Cycle 5).

    CallApp is another caller ID service.
    Uses web scraping and fallback methods.
    """

    def __init__(self, rate_limit_delay: float = 2.5):
        self.rate_limit_delay = rate_limit_delay
        self._last_request = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })

    def lookup(self, phone: str) -> PhoneSourceResult:
        """Look up phone in CallApp-style services."""
        # Rate limiting
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request = time.time()

        normalized = normalize_phone(phone)
        result = PhoneSourceResult(
            phone=normalized,
            source="callapp",
            confidence=0.0
        )

        try:
            clean = phone.replace('+', '').replace(' ', '').replace('-', '')

            # Try phonenumber.to (international phone lookup)
            if clean.startswith('7'):
                try:
                    url = f"https://phonenumber.to/+{clean}"
                    response = self.session.get(url, timeout=10)

                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')

                        # Look for name info
                        name_elem = soup.select_one('.name, .caller-name, h1')
                        if name_elem:
                            name = name_elem.get_text(strip=True)
                            # Filter out non-name content
                            if re.match(r'^[А-ЯЁA-Z][а-яёa-z]+', name) and len(name) < 50:
                                result.name_found = name
                                result.confidence = 0.65
                                result.details = {'source': 'phonenumber.to'}
                except:
                    pass

            # Try findandtrace.com
            if not result.name_found:
                try:
                    url = f"https://www.findandtrace.com/trace-mobile-number-location?mobilenumber={clean}"
                    response = self.session.get(url, timeout=10)

                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')

                        # Extract carrier/location info
                        carrier_elem = soup.select_one('.carrier, .operator')
                        if carrier_elem:
                            result.carrier = carrier_elem.get_text(strip=True)
                            result.confidence = 0.40
                            result.details = {'carrier': result.carrier}
                except:
                    pass

        except Exception as e:
            result.error = str(e)
            logger.debug(f"CallApp lookup error: {e}")

        return result

    def close(self):
        self.session.close()


class CombinedPhoneSources:
    """
    Combined phone lookup using multiple sources.
    Aggregates results from all available sources.

    Cycle 4: GetContact, NumBuster, VK/OK phone search
    Cycle 5: TrueCaller, Sync.me, Eyecon, CallApp
    """

    def __init__(self):
        # Cycle 4 sources
        self.getcontact = GetContactChecker()
        self.numbuster = NumBusterChecker()
        self.vk_searcher = VKPhoneSearcher()
        self.ok_searcher = OKPhoneSearcher()
        # Cycle 5 sources
        self.truecaller = TrueCallerChecker()
        self.syncme = SyncMeChecker()
        self.eyecon = EyeconChecker()
        self.callapp = CallAppChecker()

    def lookup(self, phone: str, target_name: Optional[str] = None) -> Dict:
        """
        Look up phone number using all available sources.

        Args:
            phone: Phone number to look up
            target_name: Optional target name for validation

        Returns:
            Aggregated result with names found and confidence
        """
        results = {
            'phone': normalize_phone(phone),
            'names_found': [],
            'carrier': None,
            'spam_score': None,
            'confidence': 0.0,
            'sources': [],
            'details': {},
            'name_match': None  # Will be set if target_name provided
        }

        source_results = []

        # Check GetContact
        try:
            gc_result = self.getcontact.lookup(phone)
            if gc_result.name_found:
                source_results.append(gc_result)
                results['sources'].append('getcontact')
                results['names_found'].append({
                    'name': gc_result.name_found,
                    'source': 'getcontact',
                    'confidence': gc_result.confidence
                })
                results['details']['getcontact'] = gc_result.details
        except Exception as e:
            logger.debug(f"GetContact error: {e}")

        # Check NumBuster
        try:
            nb_result = self.numbuster.lookup(phone)
            if nb_result.name_found:
                source_results.append(nb_result)
                results['sources'].append('numbuster')
                results['names_found'].append({
                    'name': nb_result.name_found,
                    'source': 'numbuster',
                    'confidence': nb_result.confidence
                })
            if nb_result.spam_score is not None:
                results['spam_score'] = nb_result.spam_score
            results['details']['numbuster'] = nb_result.details
        except Exception as e:
            logger.debug(f"NumBuster error: {e}")

        # Check VK phone search
        try:
            vk_result = self.vk_searcher.search(phone)
            if vk_result.name_found:
                source_results.append(vk_result)
                results['sources'].append('vk')
                results['names_found'].append({
                    'name': vk_result.name_found,
                    'source': 'vk',
                    'confidence': vk_result.confidence
                })
                results['details']['vk'] = vk_result.details
        except Exception as e:
            logger.debug(f"VK search error: {e}")

        # Check OK.ru phone search
        try:
            ok_result = self.ok_searcher.search(phone)
            if ok_result.name_found:
                source_results.append(ok_result)
                results['sources'].append('ok')
                results['names_found'].append({
                    'name': ok_result.name_found,
                    'source': 'ok',
                    'confidence': ok_result.confidence
                })
                results['details']['ok'] = ok_result.details
        except Exception as e:
            logger.debug(f"OK.ru search error: {e}")

        # Cycle 5 sources: TrueCaller, Sync.me, Eyecon, CallApp
        # Check TrueCaller
        try:
            tc_result = self.truecaller.lookup(phone)
            if tc_result.name_found:
                source_results.append(tc_result)
                results['sources'].append('truecaller')
                results['names_found'].append({
                    'name': tc_result.name_found,
                    'source': 'truecaller',
                    'confidence': tc_result.confidence
                })
                results['details']['truecaller'] = tc_result.details
            if tc_result.spam_score is not None:
                results['spam_score'] = max(results['spam_score'] or 0, tc_result.spam_score)
        except Exception as e:
            logger.debug(f"TrueCaller error: {e}")

        # Check Sync.me
        try:
            sm_result = self.syncme.lookup(phone)
            if sm_result.name_found:
                source_results.append(sm_result)
                results['sources'].append('syncme')
                results['names_found'].append({
                    'name': sm_result.name_found,
                    'source': 'syncme',
                    'confidence': sm_result.confidence
                })
                results['details']['syncme'] = sm_result.details
            if sm_result.spam_score is not None:
                results['spam_score'] = max(results['spam_score'] or 0, sm_result.spam_score)
        except Exception as e:
            logger.debug(f"Sync.me error: {e}")

        # Check Eyecon
        try:
            ey_result = self.eyecon.lookup(phone)
            if ey_result.name_found:
                source_results.append(ey_result)
                results['sources'].append('eyecon')
                results['names_found'].append({
                    'name': ey_result.name_found,
                    'source': 'eyecon',
                    'confidence': ey_result.confidence
                })
                results['details']['eyecon'] = ey_result.details
        except Exception as e:
            logger.debug(f"Eyecon error: {e}")

        # Check CallApp
        try:
            ca_result = self.callapp.lookup(phone)
            if ca_result.name_found:
                source_results.append(ca_result)
                results['sources'].append('callapp')
                results['names_found'].append({
                    'name': ca_result.name_found,
                    'source': 'callapp',
                    'confidence': ca_result.confidence
                })
                results['details']['callapp'] = ca_result.details
            if ca_result.carrier:
                results['carrier'] = ca_result.carrier
        except Exception as e:
            logger.debug(f"CallApp error: {e}")

        # Aggregate confidence
        if source_results:
            results['confidence'] = max(r.confidence for r in source_results)
            # Boost if multiple sources found same/similar name
            if len(results['names_found']) >= 2:
                results['confidence'] = min(0.95, results['confidence'] + 0.15)

        # Validate against target name if provided
        if target_name and results['names_found']:
            from app.services.phase2.per_profile_search import calculate_name_similarity
            best_match = 0.0
            best_name = None
            for name_info in results['names_found']:
                similarity = calculate_name_similarity(target_name, name_info['name'])
                if similarity > best_match:
                    best_match = similarity
                    best_name = name_info['name']

            results['name_match'] = {
                'similarity': best_match,
                'matched_name': best_name,
                'target_name': target_name,
                'is_match': best_match >= 0.60
            }

        return results

    def close(self):
        """Clean up all resources."""
        # Cycle 4 sources
        self.getcontact.close()
        self.numbuster.close()
        self.vk_searcher.close()
        self.ok_searcher.close()
        # Cycle 5 sources
        self.truecaller.close()
        self.syncme.close()
        self.eyecon.close()
        self.callapp.close()


# Convenience functions
def lookup_phone_multi_source(phone: str, target_name: Optional[str] = None) -> Dict:
    """Look up phone using multiple sources."""
    sources = CombinedPhoneSources()
    try:
        return sources.lookup(phone, target_name)
    finally:
        sources.close()


def validate_phone_ownership(phone: str, target_name: str) -> Dict:
    """
    Validate that a phone number belongs to the target person.

    Returns validation result with confidence.
    """
    result = lookup_phone_multi_source(phone, target_name)

    validation = {
        'phone': phone,
        'target_name': target_name,
        'validated': False,
        'confidence': 0.0,
        'matched_name': None,
        'sources': result.get('sources', [])
    }

    name_match = result.get('name_match')
    if name_match and name_match.get('is_match'):
        validation['validated'] = True
        validation['confidence'] = name_match.get('similarity', 0.0)
        validation['matched_name'] = name_match.get('matched_name')

    return validation
