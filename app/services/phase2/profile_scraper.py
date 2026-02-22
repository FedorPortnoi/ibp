"""
Profile Scraper Service - FIXED
================================
Extracts contact information from VK/OK/Telegram profile pages.
Now filters garbage URLs and validates extracted links.
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

from app.utils.phone import normalize_phone
from .url_validator import (
    is_valid_profile_url,
    is_reserved_username,
    is_garbage_url,
    extract_username_from_url,
    detect_platform_from_url,
    RESERVED_USERNAMES
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractedContacts:
    """Container for contacts extracted from a profile."""
    phones: List[str] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)
    websites: List[str] = field(default_factory=list)
    other_socials: List[Dict[str, str]] = field(default_factory=list)
    bio_text: str = ""


# Regex patterns for contact extraction
PHONE_PATTERNS = [
    r'\+7[\s\-\(]?\d{3}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',  # +7 999 123-45-67
    r'8[\s\-\(]?\d{3}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',    # 8 999 123-45-67
    r'\+7\d{10}',                                                  # +79991234567
    r'8\d{10}',                                                    # 89991234567
    r'\+\d{1,3}[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',  # International
]

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

SOCIAL_PATTERNS = {
    'telegram': [r't\.me/([a-zA-Z0-9_]+)', r'telegram\.me/([a-zA-Z0-9_]+)'],
    'instagram': [r'instagram\.com/([a-zA-Z0-9_.]+)', r'instagr\.am/([a-zA-Z0-9_.]+)'],
    'twitter': [r'twitter\.com/([a-zA-Z0-9_]+)', r'x\.com/([a-zA-Z0-9_]+)'],
    'facebook': [r'facebook\.com/([a-zA-Z0-9.]+)', r'fb\.com/([a-zA-Z0-9.]+)'],
    'vk': [r'vk\.com/([a-zA-Z0-9_]+)'],
    'ok': [r'ok\.ru/([a-zA-Z0-9_]+)', r'ok\.ru/profile/(\d+)'],
    'youtube': [r'youtube\.com/(?:c/|channel/|user/|@)?([a-zA-Z0-9_-]+)'],
    'tiktok': [r'tiktok\.com/@([a-zA-Z0-9_.]+)'],
    'linkedin': [r'linkedin\.com/in/([a-zA-Z0-9_-]+)'],
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}


def scrape_profile(url: str, platform: str) -> ExtractedContacts:
    """
    Scrape a profile page for contact information.
    FIXED: Now filters garbage URLs and validates extracted links.

    Args:
        url: Profile URL
        platform: 'vk', 'ok', or 'telegram'

    Returns:
        ExtractedContacts with found information
    """
    result = ExtractedContacts()

    try:
        logger.info(f"Scraping profile: {url} (platform={platform})")
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        html = response.text
        logger.info(f"Got {len(html)} bytes from {url}, status={response.status_code}")
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout scraping {url}")
        return result
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error scraping {url}: {e}")
        return result

    soup = BeautifulSoup(html, 'html.parser')

    # ===== EXTRACT BIO TEXT ONLY FROM RELEVANT SECTIONS =====
    bio_text = ""

    if platform == 'vk':
        # VK uses client-side rendering, so CSS selectors often fail
        # First try standard selectors
        bio_selectors = [
            '.profile_info_block',
            '.page_info_row',
            '.profile_info',
            '.page_block_header_extra',
            '[data-task-click="ProfileAction/status"]',
            '.page_status',
            '.profile_info_row',
        ]
        for selector in bio_selectors:
            elements = soup.select(selector)
            for el in elements:
                bio_text += " " + el.get_text(separator=' ')

        # Fallback: Try to extract from meta tags (usually still present)
        if not bio_text.strip():
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                bio_text = meta_desc['content']

            # Also try og:description
            og_desc = soup.find('meta', attrs={'property': 'og:description'})
            if og_desc and og_desc.get('content'):
                bio_text += " " + og_desc['content']

            # Try to extract from script tags containing user data
            import json
            for script in soup.find_all('script'):
                script_text = script.string or ''
                # Look for JSON data with contacts
                if 'mobile_phone' in script_text or 'home_phone' in script_text:
                    # Try to extract phone from JSON-like data
                    phone_match = re.search(r'"mobile_phone"\s*:\s*"([^"]+)"', script_text)
                    if phone_match:
                        bio_text += f" {phone_match.group(1)}"
                if 'site' in script_text and 'http' in script_text:
                    site_match = re.search(r'"site"\s*:\s*"([^"]+)"', script_text)
                    if site_match:
                        bio_text += f" {site_match.group(1)}"

            logger.info(f"VK fallback extraction used, got {len(bio_text)} chars")

    elif platform == 'ok':
        # OK: Specific profile sections
        bio_selectors = [
            '.user-profile-about',
            '.profile-user-info',
            '.user-info',
            '.profile_info',
            '.card-info',
            '.profile-hobby-info',
        ]
        for selector in bio_selectors:
            elements = soup.select(selector)
            for el in elements:
                bio_text += " " + el.get_text(separator=' ')

    elif platform == 'telegram':
        # Telegram: Channel/user description
        bio_selectors = [
            '.tgme_page_description',
            '.tgme_page_extra',
            '.tgme_header_info',
        ]
        for selector in bio_selectors:
            elements = soup.select(selector)
            for el in elements:
                bio_text += " " + el.get_text(separator=' ')

    else:
        # Fallback: Get page text but limit scope
        main_content = soup.select_one('main, article, .content, .profile, #content')
        if main_content:
            bio_text = main_content.get_text(separator=' ')
        else:
            bio_text = soup.get_text(separator=' ')

    result.bio_text = bio_text[:5000]  # Limit size
    logger.info(f"Extracted bio_text: {len(bio_text)} chars (first 200: {bio_text[:200]!r})")

    # ===== EXTRACT PHONES =====
    phones = []
    for pattern in PHONE_PATTERNS:
        matches = re.findall(pattern, bio_text)
        phones.extend(matches)

    # Normalize and deduplicate phones
    normalized_phones = []
    seen_phones = set()
    for phone in phones:
        normalized = normalize_phone(phone)
        if normalized and normalized not in seen_phones:
            # Validate: must have exactly 11 digits for Russian numbers
            digits_only = re.sub(r'\D', '', normalized)
            if len(digits_only) == 11:
                seen_phones.add(normalized)
                normalized_phones.append(normalized)

    result.phones = normalized_phones[:5]
    logger.info(f"Extracted phones: {result.phones}")

    # ===== EXTRACT EMAILS =====
    emails = list(set(re.findall(EMAIL_PATTERN, bio_text, re.IGNORECASE)))

    # Filter out garbage emails
    valid_emails = []
    for email in emails:
        email_lower = email.lower()

        # Skip image files
        if any(email_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg']):
            continue

        # Skip system emails
        system_prefixes = ['noreply', 'no-reply', 'support', 'info', 'admin',
                          'webmaster', 'contact', 'sales', 'help', 'abuse',
                          'postmaster', 'root', 'mailer-daemon', 'donotreply']
        if any(email_lower.startswith(prefix) for prefix in system_prefixes):
            continue

        # Skip example emails
        if 'example' in email_lower or 'test@' in email_lower:
            continue

        valid_emails.append(email)

    result.emails = valid_emails[:10]
    logger.info(f"Extracted emails: {result.emails}")

    # ===== EXTRACT SOCIAL LINKS - WITH VALIDATION =====
    other_socials = []

    # First, extract social links from bio text (handles escaped URLs)
    # Clean escaped backslashes common in JSON-embedded URLs
    clean_bio = bio_text.replace('\\/', '/').replace('\\"', '"')

    # Extract social links from bio text
    social_text_patterns = {
        'telegram': [r't\.me/([a-zA-Z0-9_]{5,32})', r'telegram\.me/([a-zA-Z0-9_]{5,32})'],
        'instagram': [r'instagram\.com/([a-zA-Z0-9_.]+)'],
        'twitter': [r'twitter\.com/([a-zA-Z0-9_]+)', r'x\.com/([a-zA-Z0-9_]+)'],
        'youtube': [r'youtube\.com/(?:c/|channel/|user/|@)?([a-zA-Z0-9_-]+)'],
    }

    for plat, patterns in social_text_patterns.items():
        for pattern in patterns:
            matches = re.findall(pattern, clean_bio, re.IGNORECASE)
            for username in matches:
                if username and not is_reserved_username(username):
                    if plat == 'telegram':
                        url = f'https://t.me/{username}'
                    elif plat == 'instagram':
                        url = f'https://instagram.com/{username}'
                    elif plat == 'twitter':
                        url = f'https://twitter.com/{username}'
                    elif plat == 'youtube':
                        url = f'https://youtube.com/{username}'
                    else:
                        continue

                    # Check for duplicates
                    if not any(s.get('username', '').lower() == username.lower() and s.get('platform') == plat for s in other_socials):
                        other_socials.append({
                            'platform': plat,
                            'username': username,
                            'url': url
                        })
                        logger.info(f"Extracted social from text: {plat} -> {username}")

    # Also look for links in <a> tags
    link_containers = soup.select('.profile_info a, .page_info_row a, .user-profile-about a, '
                                  '.tgme_page_description a, .profile_info_block a, .user-info a')

    # Fallback: all links but filter aggressively
    if not link_containers:
        link_containers = soup.select('a[href]')

    for link in link_containers:
        href = link.get('href', '')
        if not href:
            continue

        # Make absolute URL
        if href.startswith('/'):
            # Skip internal navigation links
            if any(p in href.lower() for p in ['/search', '/settings', '/login', '/help', '/privacy']):
                continue
            continue  # Skip relative links entirely

        # Validate as social profile
        if not is_valid_profile_url(href):
            continue

        detected_platform = detect_platform_from_url(href)
        if not detected_platform:
            continue

        # Skip if same platform as source (we're scraping this profile already)
        if detected_platform == platform:
            continue

        username = extract_username_from_url(href, detected_platform)
        if not username or is_reserved_username(username):
            continue

        # Check for duplicates
        href_normalized = href.lower().rstrip('/')
        if any(s.get('url', '').lower().rstrip('/') == href_normalized for s in other_socials):
            continue

        other_socials.append({
            'platform': detected_platform,
            'username': username,
            'url': href
        })

    result.other_socials = other_socials[:10]
    logger.info(f"Extracted other_socials: {result.other_socials}")
    logger.info(f"Profile scrape complete for {url}: {len(result.phones)} phones, {len(result.emails)} emails, {len(result.other_socials)} socials")

    return result


def get_domain(platform: str) -> str:
    """Get domain for platform."""
    domains = {
        'telegram': 't.me',
        'instagram': 'instagram.com',
        'twitter': 'twitter.com',
        'facebook': 'facebook.com',
        'vk': 'vk.com',
        'ok': 'ok.ru',
        'youtube': 'youtube.com',
        'tiktok': 'tiktok.com',
        'linkedin': 'linkedin.com',
    }
    return domains.get(platform, '')


def extract_bio(soup: BeautifulSoup, platform: str) -> str:
    """Extract bio/about section based on platform."""
    bio = ""

    if platform == 'vk':
        # VK bio selectors
        selectors = [
            '.profile_info',
            '.pp_info',
            '.page_info_row',
            '.ProfileInfo',
            '.page_block_description',
            '#profile_info',
        ]
        for sel in selectors:
            elem = soup.select_one(sel)
            if elem:
                bio = elem.get_text(separator=' ', strip=True)
                if bio:
                    break

    elif platform == 'telegram':
        # Telegram bio
        selectors = [
            '.tgme_page_description',
            '.tgme_page_extra',
            '[class*="description"]',
        ]
        for sel in selectors:
            elem = soup.select_one(sel)
            if elem:
                bio = elem.get_text(separator=' ', strip=True)
                if bio:
                    break

    elif platform == 'ok':
        # OK bio
        selectors = [
            '.user-profile-about',
            '.profile-user-info',
            '.user-info',
            '.profile-info',
            '[class*="about"]',
        ]
        for sel in selectors:
            elem = soup.select_one(sel)
            if elem:
                bio = elem.get_text(separator=' ', strip=True)
                if bio:
                    break

    # Fallback: try common patterns
    if not bio:
        meta_desc = soup.select_one('meta[name="description"]')
        if meta_desc:
            bio = meta_desc.get('content', '')

    return bio


def scrape_multiple_profiles(profiles: List[Dict]) -> Dict[str, ExtractedContacts]:
    """
    Scrape multiple profiles.

    Args:
        profiles: List of dicts with 'url' and 'platform' keys

    Returns:
        Dict mapping URLs to ExtractedContacts
    """
    results = {}
    for profile in profiles:
        url = profile.get('url', '')
        platform = profile.get('platform', '').lower()
        if url:
            results[url] = scrape_profile(url, platform)
    return results
