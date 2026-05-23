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
COUNTRY_CODE = 'RU'
CIS_COUNTRY_CODES = frozenset((
    'RU', 'BY', 'KZ', 'UA', 'UZ', 'KG', 'TJ', 'TM', 'AZ', 'AM', 'GE', 'MD',
))

# Locale
LOCALE = 'ru-RU'
TIMEZONE = 'Europe/Moscow'
LANGUAGE_CODE = 'ru'

# Currency / payments
CURRENCY = 'RUB'
PAYMENT_METHODS = ('SBP', 'MIR', 'invoice')

# Phone
PHONE_PREFIX = '+7'
PHONE_COUNTRY_CODE = '7'

# Compliance (152-FZ Personal Data Law)
PERSONAL_DATA_LAW = '152-FZ'
DATA_LOCALIZATION_REQUIRED = True
CONSENT_REQUIRED = True
