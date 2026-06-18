"""Shared money utility functions for parsing and formatting Russian ruble amounts."""

import re
from typing import Optional


def parse_rub_amount(text: str) -> Optional[float]:
    """Parse monetary amount from a Russian ruble text string.

    Handles formats like '1 234 567,89 руб.', '1\xa0234\xa0567,89', '12345.67', etc.
    Returns None for None/empty/unparseable input (not 0.0, so callers can
    distinguish 'not found' from 'zero').
    """
    if not text:
        return None
    # Try regex that handles spaced thousands and comma decimal separator
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


def fmt_rub(value: Optional[float]) -> str:
    """Format a float/int as a human-readable Russian ruble string.

    Examples:
        1_500_000_000_000 -> '1.5 трлн ₽'
        2_300_000_000     -> '2.3 млрд ₽'
        5_700_000         -> '5.7 млн ₽'
        123_456           -> '123 456 ₽'
        None / 0 / negative -> ''
    """
    if not value or value <= 0:
        return ''
    if value >= 1_000_000_000_000:
        return f'{value / 1_000_000_000_000:.1f} трлн ₽'
    if value >= 1_000_000_000:
        return f'{value / 1_000_000_000:.1f} млрд ₽'
    if value >= 1_000_000:
        return f'{value / 1_000_000:.1f} млн ₽'
    return f'{value:,.0f} ₽'.replace(',', ' ')


def parse_accounting_cell(text: str) -> Optional[int]:
    """Parse a Russian accounting cell where values are in thousands of RUB.

    Handles formats used by bo.nalog.ru:
    - '1 234' -> 1_234_000
    - '(567)' -> -567_000  (parentheses = negative)
    - '-' or '—' or '' -> None
    Returns integer RUB (thousands * 1000), or None if unparseable.
    """
    if not text or text.strip() in ('-', '—', ''):
        return None
    cleaned = re.sub(r'[^\d\-]', '', text.replace('(', '-').replace(')', ''))
    try:
        val = int(cleaned)
        return val * 1000
    except (ValueError, OverflowError):
        return None
