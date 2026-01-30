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


class CrossValidator:
    """
    Main cross-validation orchestrator.

    Combines phone→name and email→social validation.
    """

    def __init__(self):
        self.phone_validator = PhoneNameValidator()
        self._email_validator = None  # Will be added in Cycle 8

    def validate_phone(self, phone: str, target_name: str) -> ValidationResult:
        """Validate a phone number against target name."""
        return self.phone_validator.validate_phone(phone, target_name)

    def validate_phones(self, phones: List[str], target_name: str) -> List[ValidationResult]:
        """Validate multiple phones against target name."""
        return self.phone_validator.validate_phones(phones, target_name)

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

    def close(self):
        """Clean up all resources."""
        self.phone_validator.close()


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
