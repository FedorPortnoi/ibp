# 003 — Russia Market Profile

**Date:** 2026-05-23
**Status:** Decided

## What we chose

Russia-specific constants and compliance markers live in `app/market/russia.py`.
No hardcoded `'RUB'`, `'+7'`, `'Europe/Moscow'`, or `'152-FZ'` strings scattered
across routes and services.

```python
# app/market/russia.py
CURRENCY = 'RUB'
LOCALE = 'ru-RU'
TIMEZONE = 'Europe/Moscow'
PHONE_PREFIX = '+7'
CIS_COUNTRY_CODES = frozenset(('RU', 'BY', 'KZ', ...))
PERSONAL_DATA_LAW = '152-FZ'
CONSENT_REQUIRED = True
PAYMENT_METHODS = ('SBP', 'MIR', 'invoice')
```

Russia-specific logic (INN checksum, phone normalization) stays in `app/utils/`
because it is pure algorithmic code, not config. `app/market/russia.py` imports
and re-exports these for callers who want everything from one place.

## Why

IBP is Russia-first. Every part of the product makes Russia-specific assumptions:
INN as primary identifier, +7 phone format, 152-FZ consent, RUB pricing, SBP/MIR
payment methods, CIS language detection, Yandex/VK/Telegram integrations.

Before this change, these assumptions were hardcoded in:
- `app/routes/auth.py` (CIS country codes for language detection)
- `app/models/candidate_check.py` (INN field)
- `app/services/phase2/russian_phone_validator.py` (phone format)
- `app/models/candidate_check.py` (pd_consent field for 152-FZ)

Centralizing them means: when IBP expands to a second market, the market-specific
behavior is in one place, not scattered across every file.

## Tradeoff accepted

This is a config module, not a plugin system. IBP does not support multiple
simultaneous markets. If it ever does (e.g., Kazakhstan with different compliance
rules), `market/russia.py` becomes `market/russia.py` + `market/kz.py` + a
market-selection layer. That extension is straightforward from the current shape.

## Rule going forward

- New Russia-specific constants go in `app/market/russia.py`.
- No bare string literals for currencies, timezones, country codes, or compliance
  law names anywhere outside `market/russia.py`.
- When adding a second-market feature, create `market/<country>.py` and select
  via config, not via scattered if-statements.
