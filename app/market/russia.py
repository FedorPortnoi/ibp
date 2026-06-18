"""
Russia market profile.

Single source of truth for Russia-specific constants and compliance markers.
All Russia-specific behavior should enter through this module — not be hardcoded
across routes, services, or templates.

For INN validation and phone normalization (algorithmic code, not config) see:
  app/utils/inn_validator.py
  app/utils/phone.py
"""

# Geographic
CIS_COUNTRY_CODES = frozenset((
    'RU', 'BY', 'KZ', 'UA', 'UZ', 'KG', 'TJ', 'TM', 'AZ', 'AM', 'GE', 'MD',
))
