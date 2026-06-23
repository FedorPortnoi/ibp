"""
Shared utilities for court and company services.
"""

# ---------------------------------------------------------------------------
# Court category normalisation
# ---------------------------------------------------------------------------

COURT_CATEGORY_MAP: dict[str, str] = {
    'гражданские': 'гражданское',
    'уголовные': 'уголовное',
    'административные': 'административное',
    'арбитражные': 'арбитражное',
}

# ---------------------------------------------------------------------------
# BeautifulSoup <li> label extractor
# ---------------------------------------------------------------------------


def get_li_value(card, label: str) -> str:
    """Extract the <p> text from a <li> whose <span> contains *label*."""
    for li in card.select('li'):
        span = li.select_one('span')
        if span and label in span.get_text(strip=True):
            p = li.select_one('p')
            return p.get_text(strip=True) if p else ''
    return ''


# ---------------------------------------------------------------------------
# Legal-entity type detection
# ---------------------------------------------------------------------------


def detect_company_type(name: str) -> str:
    """Return the legal-entity type prefix found in *name* (e.g. 'ООО', 'ИП').

    Checks in order: ПАО, ОАО, ЗАО, АО, ООО, НКО, ГУП, МУП, ИП.  Returns '' if none matched.
    """
    n = name.upper()
    for t in ('ПАО', 'ОАО', 'ЗАО', 'АО', 'ООО', 'НКО', 'ГУП', 'МУП', 'ИП'):
        if t in n:
            return t
    return ''
