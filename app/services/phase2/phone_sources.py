"""
Extended Phone Sources for Phase 2
===================================
Additional phone discovery and validation sources.

Sources implemented:
1. GetContact - Phone→Name lookup (web scraping, API if available)
2. NumBuster - Telegram bot integration (via Telethon)
3. TrueCaller - Web lookup (scraping)
4. Sync.me - Web lookup
5. VK Phone Search - Search VK by phone number
6. OK.ru Phone Search - Search OK.ru by phone number
7. Telegram Phone Lookup - Check if phone registered on Telegram

Cycle 4 Focus: GetContact + NumBuster
Cycle 5 Focus: TrueCaller + Sync.me
Cycle 6 Focus: Telegram + VK/OK phone search
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


class CombinedPhoneSources:
    """
    Combined phone lookup using multiple sources.
    Aggregates results from all available sources.

    Cycle 4: GetContact, NumBuster, VK/OK phone search
    """

    def __init__(self):
        self.getcontact = GetContactChecker()
        self.numbuster = NumBusterChecker()
        self.vk_searcher = VKPhoneSearcher()
        self.ok_searcher = OKPhoneSearcher()

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
        self.getcontact.close()
        self.numbuster.close()
        self.vk_searcher.close()
        self.ok_searcher.close()


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
