"""
Cross-Validation Service for Phase 2
=====================================
Validates discovered contact information against target identity.

Cycle 7: Phone→Name validation
Cycle 8: Email→Social validation

Methods:
1. Phone→Name: Look up phone in caller ID services, compare name to target
2. Email→Social: Check if email is linked to social profiles, verify identity
3. Multi-source validation: Aggregate results from multiple sources
"""

import logging
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of cross-validation."""
    item: str  # phone or email
    item_type: str  # 'phone' or 'email'
    target_name: str
    validated: bool = False
    confidence: float = 0.0
    matched_name: Optional[str] = None
    name_similarity: float = 0.0
    sources_checked: List[str] = field(default_factory=list)
    sources_matched: List[str] = field(default_factory=list)
    details: Dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


def calculate_name_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity between two names.

    Handles:
    - Case insensitivity
    - Cyrillic/Latin transliteration
    - Name part matching (first, last, patronymic)
    - Diminutive forms

    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not name1 or not name2:
        return 0.0

    # Normalize names
    n1 = _normalize_name(name1)
    n2 = _normalize_name(name2)

    if not n1 or not n2:
        return 0.0

    # Direct match
    if n1 == n2:
        return 1.0

    # Split into parts
    parts1 = n1.split()
    parts2 = n2.split()

    # Calculate similarity
    scores = []

    # Sequence matcher on full names
    full_sim = SequenceMatcher(None, n1, n2).ratio()
    scores.append(full_sim)

    # Part-by-part matching
    if len(parts1) >= 1 and len(parts2) >= 1:
        # Match first parts (usually first name)
        first_sim = SequenceMatcher(None, parts1[0], parts2[0]).ratio()
        scores.append(first_sim * 1.2)  # Weight first name higher

        # Check if one name is a diminutive of another
        diminutive_match = _check_diminutive_match(parts1[0], parts2[0])
        if diminutive_match:
            scores.append(0.85)

    if len(parts1) >= 2 and len(parts2) >= 2:
        # Match last parts (usually last name)
        last_sim = SequenceMatcher(None, parts1[-1], parts2[-1]).ratio()
        scores.append(last_sim * 1.3)  # Weight last name highest

    # Cross-match parts (in case order is different)
    for p1 in parts1:
        for p2 in parts2:
            if len(p1) >= 3 and len(p2) >= 3:
                part_sim = SequenceMatcher(None, p1, p2).ratio()
                if part_sim > 0.8:
                    scores.append(part_sim)

    # Return highest score, capped at 1.0
    return min(1.0, max(scores) if scores else 0.0)


def _normalize_name(name: str) -> str:
    """Normalize name for comparison."""
    if not name:
        return ""

    # Convert to lowercase
    name = name.lower().strip()

    # Remove special characters but keep letters (Cyrillic and Latin)
    name = re.sub(r'[^\w\s]', '', name, flags=re.UNICODE)

    # Replace multiple spaces with single
    name = re.sub(r'\s+', ' ', name)

    return name


def _check_diminutive_match(name1: str, name2: str) -> bool:
    """Check if names are diminutive forms of each other."""
    # Common Russian diminutive mappings
    diminutives = {
        'александр': ['саша', 'шура', 'саня', 'алекс'],
        'алексей': ['леша', 'алеша', 'леха'],
        'анастасия': ['настя', 'ася', 'стася'],
        'анна': ['аня', 'анюта', 'нюра'],
        'дмитрий': ['дима', 'митя'],
        'екатерина': ['катя', 'катюша'],
        'елена': ['лена', 'леночка'],
        'иван': ['ваня', 'ванюша'],
        'мария': ['маша', 'маруся'],
        'михаил': ['миша', 'мишка'],
        'николай': ['коля', 'николаша'],
        'ольга': ['оля', 'олюшка'],
        'павел': ['паша', 'пашка'],
        'петр': ['петя', 'петруша'],
        'сергей': ['сережа', 'серега'],
        'татьяна': ['таня', 'танюша'],
        'федор': ['федя', 'федька'],
        'юлия': ['юля', 'юлечка'],
        'даниил': ['даня', 'данила', 'данечка'],
        'алена': ['аленка', 'аленушка'],
        'ангелина': ['геля', 'лина', 'ангел'],
        'тихон': ['тиша', 'тишка'],
    }

    n1 = name1.lower()
    n2 = name2.lower()

    # Check direct mapping
    for full, dims in diminutives.items():
        if n1 == full and n2 in dims:
            return True
        if n2 == full and n1 in dims:
            return True
        if n1 in dims and n2 in dims:
            return True

    # Check if one starts with the other (common diminutive pattern)
    if len(n1) >= 3 and len(n2) >= 3:
        if n1.startswith(n2[:3]) or n2.startswith(n1[:3]):
            return True

    return False


class PhoneNameValidator:
    """
    Validate phone numbers by looking up associated names.

    Cycle 7: Core phone→name validation.
    """

    def __init__(self):
        # Lazy import to avoid circular dependencies
        self._phone_sources = None

    def _get_phone_sources(self):
        """Lazy load phone sources."""
        if self._phone_sources is None:
            from app.services.phase2.phone_sources import CombinedPhoneSources
            self._phone_sources = CombinedPhoneSources()
        return self._phone_sources

    def validate_phone(self, phone: str, target_name: str) -> ValidationResult:
        """
        Validate that a phone number belongs to the target person.

        Args:
            phone: Phone number to validate
            target_name: Expected owner's name

        Returns:
            ValidationResult with confidence score
        """
        result = ValidationResult(
            item=phone,
            item_type='phone',
            target_name=target_name
        )

        try:
            # Look up phone in multiple sources
            sources = self._get_phone_sources()
            lookup_result = sources.lookup(phone, target_name=target_name)

            result.sources_checked = lookup_result.get('sources', [])
            result.details = lookup_result.get('details', {})

            # Get all names found
            names_found = lookup_result.get('names_found', [])

            if names_found:
                # Find best matching name
                best_similarity = 0.0
                best_name = None
                best_source = None

                for name_info in names_found:
                    name = name_info.get('name', '')
                    source = name_info.get('source', '')

                    similarity = calculate_name_similarity(target_name, name)

                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_name = name
                        best_source = source

                result.matched_name = best_name
                result.name_similarity = best_similarity

                # Determine validation status
                if best_similarity >= 0.80:
                    result.validated = True
                    result.confidence = min(0.95, best_similarity * 1.1)
                    result.sources_matched = [best_source]
                    logger.info(f"Phone {phone} validated: '{best_name}' matches '{target_name}' ({best_similarity:.2f})")
                elif best_similarity >= 0.60:
                    result.validated = True
                    result.confidence = best_similarity * 0.9
                    result.sources_matched = [best_source]
                    logger.info(f"Phone {phone} likely match: '{best_name}' ~ '{target_name}' ({best_similarity:.2f})")
                elif best_similarity >= 0.40:
                    result.validated = False
                    result.confidence = best_similarity * 0.5
                    logger.info(f"Phone {phone} weak match: '{best_name}' vs '{target_name}' ({best_similarity:.2f})")
                else:
                    result.validated = False
                    result.confidence = 0.0
                    logger.info(f"Phone {phone} no match: '{best_name}' != '{target_name}' ({best_similarity:.2f})")
            else:
                # No names found in any source
                result.validated = False
                result.confidence = 0.0
                logger.debug(f"Phone {phone}: No names found in any source")

        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"Phone validation error for {phone}: {e}")

        return result

    def validate_phones(self, phones: List[str], target_name: str) -> List[ValidationResult]:
        """
        Validate multiple phone numbers.

        Args:
            phones: List of phone numbers
            target_name: Expected owner's name

        Returns:
            List of ValidationResult for each phone
        """
        results = []
        for phone in phones:
            result = self.validate_phone(phone, target_name)
            results.append(result)
        return results

    def close(self):
        """Clean up resources."""
        if self._phone_sources:
            self._phone_sources.close()


class EmailSocialValidator:
    """
    Validate emails by checking associated social profiles.

    Cycle 8: Email→Social validation.

    Methods:
    1. Check if email is linked to VK/OK profiles
    2. Check Gravatar for profile info
    3. Check if email appears in GitHub commits
    4. Validate email domain and format
    """

    def __init__(self):
        self._email_sources = None
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def _get_email_sources(self):
        """Lazy load email sources."""
        if self._email_sources is None:
            try:
                from app.services.phase2.email_sources import CombinedEmailSources
                self._email_sources = CombinedEmailSources()
            except ImportError:
                self._email_sources = None
        return self._email_sources

    def validate_email(self, email: str, target_name: str, profile_url: Optional[str] = None) -> ValidationResult:
        """
        Validate that an email belongs to the target person.

        Args:
            email: Email address to validate
            target_name: Expected owner's name
            profile_url: Optional social profile URL to check against

        Returns:
            ValidationResult with confidence score
        """
        result = ValidationResult(
            item=email,
            item_type='email',
            target_name=target_name
        )

        try:
            # Method 1: Check Gravatar for profile info
            gravatar_result = self._check_gravatar(email)
            if gravatar_result:
                result.sources_checked.append('gravatar')
                name = gravatar_result.get('name', '')
                if name:
                    similarity = calculate_name_similarity(target_name, name)
                    if similarity > result.name_similarity:
                        result.name_similarity = similarity
                        result.matched_name = name
                        result.details['gravatar'] = gravatar_result
                        if similarity >= 0.60:
                            result.sources_matched.append('gravatar')

            # Method 2: Check email sources (Epieos, Hunter.io, etc.)
            email_sources = self._get_email_sources()
            if email_sources:
                try:
                    # Check Epieos for Google account info
                    epieos_result = email_sources.epieos.check(email)
                    if epieos_result and epieos_result.get('exists'):
                        result.sources_checked.append('epieos')
                        name = epieos_result.get('name', '')
                        if name:
                            similarity = calculate_name_similarity(target_name, name)
                            if similarity > result.name_similarity:
                                result.name_similarity = similarity
                                result.matched_name = name
                            result.details['epieos'] = epieos_result
                            if similarity >= 0.60:
                                result.sources_matched.append('epieos')
                except Exception as e:
                    logger.debug(f"Epieos check error: {e}")

            # Method 3: Check if email domain matches profile domain
            if profile_url:
                domain_match = self._check_domain_match(email, profile_url)
                if domain_match:
                    result.details['domain_match'] = True
                    result.sources_checked.append('domain_match')
                    if domain_match.get('confidence', 0) >= 0.5:
                        result.sources_matched.append('domain_match')

            # Method 4: Check GitHub for email in commits
            github_result = self._check_github_email(email)
            if github_result:
                result.sources_checked.append('github')
                name = github_result.get('name', '')
                if name:
                    similarity = calculate_name_similarity(target_name, name)
                    if similarity > result.name_similarity:
                        result.name_similarity = similarity
                        result.matched_name = name
                    result.details['github'] = github_result
                    if similarity >= 0.60:
                        result.sources_matched.append('github')

            # Method 5: Check VK/OK for email association
            social_result = self._check_social_email(email, target_name)
            if social_result:
                result.sources_checked.extend(social_result.get('sources', []))
                name = social_result.get('matched_name', '')
                if name:
                    similarity = social_result.get('similarity', 0)
                    if similarity > result.name_similarity:
                        result.name_similarity = similarity
                        result.matched_name = name
                    if similarity >= 0.60:
                        result.sources_matched.extend(social_result.get('sources', []))
                result.details['social'] = social_result

            # Calculate final validation result
            if result.name_similarity >= 0.80:
                result.validated = True
                result.confidence = min(0.95, result.name_similarity * 1.1)
            elif result.name_similarity >= 0.60:
                result.validated = True
                result.confidence = result.name_similarity * 0.9
            elif result.sources_matched:
                # Some sources matched but name similarity is low
                result.validated = True
                result.confidence = 0.50 + (len(result.sources_matched) * 0.1)
            elif result.name_similarity >= 0.40:
                result.validated = False
                result.confidence = result.name_similarity * 0.5
            else:
                result.validated = False
                result.confidence = 0.0

        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"Email validation error for {email}: {e}")

        return result

    def _check_gravatar(self, email: str) -> Optional[Dict]:
        """Check Gravatar for profile information."""
        import hashlib

        try:
            # Gravatar uses MD5 hash of lowercase email
            email_hash = hashlib.md5(email.lower().strip().encode()).hexdigest()
            url = f"https://www.gravatar.com/{email_hash}.json"

            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if 'entry' in data and data['entry']:
                    entry = data['entry'][0]
                    return {
                        'exists': True,
                        'name': entry.get('displayName', '') or entry.get('preferredUsername', ''),
                        'profile_url': entry.get('profileUrl', ''),
                        'photos': [p.get('value') for p in entry.get('photos', [])],
                        'accounts': [a.get('domain') for a in entry.get('accounts', [])]
                    }

        except Exception as e:
            logger.debug(f"Gravatar check error: {e}")

        return None

    def _check_github_email(self, email: str) -> Optional[Dict]:
        """Check if email appears in GitHub commits."""
        try:
            # Search GitHub for commits with this email
            url = f"https://api.github.com/search/commits?q=author-email:{email}"
            headers = {'Accept': 'application/vnd.github.cloak-preview'}

            response = self.session.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                data = response.json()
                if data.get('total_count', 0) > 0:
                    items = data.get('items', [])
                    if items:
                        commit = items[0]
                        author = commit.get('author', {}) or {}
                        return {
                            'exists': True,
                            'name': author.get('login', ''),
                            'commit_count': data.get('total_count', 0),
                            'github_url': author.get('html_url', '')
                        }

        except Exception as e:
            logger.debug(f"GitHub email check error: {e}")

        return None

    def _check_domain_match(self, email: str, profile_url: str) -> Optional[Dict]:
        """Check if email domain matches profile URL domain."""
        try:
            import re
            from urllib.parse import urlparse

            # Extract email domain
            email_domain = email.split('@')[-1].lower() if '@' in email else ''

            # Extract profile domain
            parsed = urlparse(profile_url)
            profile_domain = parsed.netloc.lower()

            # Check for match
            if email_domain and profile_domain:
                # Direct match
                if email_domain in profile_domain or profile_domain in email_domain:
                    return {'confidence': 0.7, 'email_domain': email_domain, 'profile_domain': profile_domain}

                # Check for common username-based emails
                username_match = re.search(r'(?:id|user)?(\d+|[a-z_]+)', profile_url, re.I)
                if username_match:
                    username = username_match.group(1)
                    if username.lower() in email.lower():
                        return {'confidence': 0.5, 'username_match': username}

        except Exception as e:
            logger.debug(f"Domain match error: {e}")

        return None

    def _check_social_email(self, email: str, target_name: str) -> Optional[Dict]:
        """Check if email is associated with VK/OK profiles."""
        results = {'sources': [], 'matched_name': None, 'similarity': 0.0}

        try:
            # Try VK email search
            vk_result = self._search_vk_by_email(email, target_name)
            if vk_result:
                results['sources'].append('vk')
                if vk_result.get('similarity', 0) > results['similarity']:
                    results['similarity'] = vk_result['similarity']
                    results['matched_name'] = vk_result.get('name')
                results['vk'] = vk_result

            # Try OK email search
            ok_result = self._search_ok_by_email(email, target_name)
            if ok_result:
                results['sources'].append('ok')
                if ok_result.get('similarity', 0) > results['similarity']:
                    results['similarity'] = ok_result['similarity']
                    results['matched_name'] = ok_result.get('name')
                results['ok'] = ok_result

        except Exception as e:
            logger.debug(f"Social email check error: {e}")

        return results if results['sources'] else None

    def _search_vk_by_email(self, email: str, target_name: str) -> Optional[Dict]:
        """Search VK for profiles with this email."""
        try:
            from bs4 import BeautifulSoup

            # VK search doesn't directly search by email, but we can try
            url = f"https://vk.com/search?c[q]={email}&c[section]=people"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for results
                results = soup.select('.people_row, .search_row')
                if results:
                    first = results[0]
                    name_elem = first.select_one('.people_name, .search_name a')
                    if name_elem:
                        name = name_elem.get_text(strip=True)
                        similarity = calculate_name_similarity(target_name, name)
                        return {
                            'name': name,
                            'similarity': similarity,
                            'source': 'vk_search'
                        }

        except Exception as e:
            logger.debug(f"VK email search error: {e}")

        return None

    def _search_ok_by_email(self, email: str, target_name: str) -> Optional[Dict]:
        """Search OK.ru for profiles with this email."""
        try:
            from bs4 import BeautifulSoup

            # OK.ru search
            url = f"https://ok.ru/search?st.query={email}&st.cmd=friendsFriends"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for results
                results = soup.select('.user-card, .ucard')
                if results:
                    first = results[0]
                    name_elem = first.select_one('.user-card_name, .ucard__name')
                    if name_elem:
                        name = name_elem.get_text(strip=True)
                        similarity = calculate_name_similarity(target_name, name)
                        return {
                            'name': name,
                            'similarity': similarity,
                            'source': 'ok_search'
                        }

        except Exception as e:
            logger.debug(f"OK email search error: {e}")

        return None

    def validate_emails(self, emails: List[str], target_name: str) -> List[ValidationResult]:
        """Validate multiple emails."""
        results = []
        for email in emails:
            result = self.validate_email(email, target_name)
            results.append(result)
        return results

    def close(self):
        """Clean up resources."""
        self.session.close()
        if self._email_sources:
            try:
                self._email_sources.close()
            except:
                pass


class CrossValidator:
    """
    Main cross-validation orchestrator.

    Combines phone→name and email→social validation.
    Cycle 7: Phone validation
    Cycle 8: Email validation
    """

    def __init__(self):
        self.phone_validator = PhoneNameValidator()
        self.email_validator = EmailSocialValidator()

    def validate_phone(self, phone: str, target_name: str) -> ValidationResult:
        """Validate a phone number against target name."""
        return self.phone_validator.validate_phone(phone, target_name)

    def validate_phones(self, phones: List[str], target_name: str) -> List[ValidationResult]:
        """Validate multiple phones against target name."""
        return self.phone_validator.validate_phones(phones, target_name)

    def validate_email(self, email: str, target_name: str, profile_url: Optional[str] = None) -> ValidationResult:
        """Validate an email against target name and optional profile."""
        return self.email_validator.validate_email(email, target_name, profile_url)

    def validate_emails(self, emails: List[str], target_name: str) -> List[ValidationResult]:
        """Validate multiple emails against target name."""
        return self.email_validator.validate_emails(emails, target_name)

    def get_validated_phones(
        self,
        phones: List[str],
        target_name: str,
        min_confidence: float = 0.60
    ) -> List[Tuple[str, float]]:
        """
        Get phones that pass validation with minimum confidence.

        Args:
            phones: List of phone numbers to validate
            target_name: Target person's name
            min_confidence: Minimum confidence threshold

        Returns:
            List of (phone, confidence) tuples that passed validation
        """
        validated = []
        results = self.validate_phones(phones, target_name)

        for result in results:
            if result.validated and result.confidence >= min_confidence:
                validated.append((result.item, result.confidence))

        # Sort by confidence descending
        validated.sort(key=lambda x: x[1], reverse=True)
        return validated

    def get_validated_emails(
        self,
        emails: List[str],
        target_name: str,
        min_confidence: float = 0.60
    ) -> List[Tuple[str, float]]:
        """
        Get emails that pass validation with minimum confidence.

        Args:
            emails: List of emails to validate
            target_name: Target person's name
            min_confidence: Minimum confidence threshold

        Returns:
            List of (email, confidence) tuples that passed validation
        """
        validated = []
        results = self.validate_emails(emails, target_name)

        for result in results:
            if result.validated and result.confidence >= min_confidence:
                validated.append((result.item, result.confidence))

        # Sort by confidence descending
        validated.sort(key=lambda x: x[1], reverse=True)
        return validated

    def validate_all(
        self,
        phones: List[str],
        emails: List[str],
        target_name: str
    ) -> Dict[str, List[ValidationResult]]:
        """
        Validate all contact information.

        Returns:
            Dict with 'phones' and 'emails' keys containing validation results
        """
        return {
            'phones': self.validate_phones(phones, target_name),
            'emails': self.validate_emails(emails, target_name)
        }

    def close(self):
        """Clean up all resources."""
        self.phone_validator.close()
        self.email_validator.close()


# Convenience functions
def validate_phone_ownership(phone: str, target_name: str) -> ValidationResult:
    """Convenience function to validate a single phone."""
    validator = PhoneNameValidator()
    try:
        return validator.validate_phone(phone, target_name)
    finally:
        validator.close()


def validate_phones_batch(phones: List[str], target_name: str) -> List[ValidationResult]:
    """Convenience function to validate multiple phones."""
    validator = PhoneNameValidator()
    try:
        return validator.validate_phones(phones, target_name)
    finally:
        validator.close()


def get_validated_phones(
    phones: List[str],
    target_name: str,
    min_confidence: float = 0.60
) -> List[Tuple[str, float]]:
    """Convenience function to get validated phones above threshold."""
    validator = CrossValidator()
    try:
        return validator.get_validated_phones(phones, target_name, min_confidence)
    finally:
        validator.close()


# Email validation convenience functions (Cycle 8)
def validate_email_ownership(email: str, target_name: str, profile_url: Optional[str] = None) -> ValidationResult:
    """Convenience function to validate a single email."""
    validator = EmailSocialValidator()
    try:
        return validator.validate_email(email, target_name, profile_url)
    finally:
        validator.close()


def validate_emails_batch(emails: List[str], target_name: str) -> List[ValidationResult]:
    """Convenience function to validate multiple emails."""
    validator = EmailSocialValidator()
    try:
        return validator.validate_emails(emails, target_name)
    finally:
        validator.close()


def get_validated_emails(
    emails: List[str],
    target_name: str,
    min_confidence: float = 0.60
) -> List[Tuple[str, float]]:
    """Convenience function to get validated emails above threshold."""
    validator = CrossValidator()
    try:
        return validator.get_validated_emails(emails, target_name, min_confidence)
    finally:
        validator.close()


def validate_all_contacts(
    phones: List[str],
    emails: List[str],
    target_name: str
) -> Dict[str, List[ValidationResult]]:
    """Convenience function to validate all contact info."""
    validator = CrossValidator()
    try:
        return validator.validate_all(phones, emails, target_name)
    finally:
        validator.close()
