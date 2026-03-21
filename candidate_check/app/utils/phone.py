"""
Canonical phone normalization for Russian numbers.

This is the single source of truth for normalize_phone().
All other modules delegate to this implementation.
"""

import re


def normalize_phone(phone: str) -> str:
    """Canonical phone normalization for Russian numbers.

    Converts various formats to +7XXXXXXXXXX.
    Returns original string if cannot normalize.
    Returns '' for empty/None input.

    Args:
        phone: Phone number in any format, or None.

    Returns:
        Normalized phone string in +7XXXXXXXXXX format,
        original string if not normalizable,
        or empty string for empty/None input.
    """
    if not phone:
        return ''

    # Strip everything except digits
    digits = re.sub(r'\D', '', phone)

    # Handle Russian formats
    if len(digits) == 11:
        if digits.startswith('8'):
            return '+7' + digits[1:]
        elif digits.startswith('7'):
            return '+' + digits
    elif len(digits) == 10:
        return '+7' + digits

    # Can't normalize -- return original
    return phone
