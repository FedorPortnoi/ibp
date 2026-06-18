"""
Yandex People Search — Phase 1 (Playwright)
============================================
Searches yandex.ru/people for social media profiles matching a name.
Uses Playwright browser to bypass SmartCaptcha blocking.

Extracts links to VK, Telegram, WhatsApp, Max, OK from Yandex People cards.
Handles SmartCaptcha gracefully — returns empty results if blocked.
"""

import logging
import random
import re
import time
import traceback
from typing import List, Dict, Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

# Target social media domains to extract from Yandex People results
TARGET_DOMAINS = {
    'vk.com': 'vk',
    't.me': 'telegram',
    'wa.me': 'whatsapp',
    'max.ru': 'max',
    'ok.ru': 'ok',
    'instagram.com': 'instagram',
    'facebook.com': 'facebook',
}

# Reserved URL paths that aren't user profiles
RESERVED_PATHS = {
    'search', 'login', 'feed', 'groups', 'public', 'about', 'help',
    'terms', 'privacy', 'faq', 'support', 'settings', 'menu', 'share',
    'away', 'wall', 'photo', 'video', 'audio', 'board', 'market',
    'friends', 'groups_list', 'apps', 'docs', 'im', 'mail',
}

# User agent for browser context
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/131.0.0.0 Safari/537.36'
)

# Yandex People URL patterns to try
YANDEX_PEOPLE_URLS = [
    'https://yandex.ru/people?query={query}',
    'https://yandex.ru/people/search?text={query}',
]

MAX_RESULTS = 100
