"""Telegram username search service."""

import requests
import re


def check_telegram_username(username: str) -> dict:
    """Check if Telegram account exists and get profile info."""
    url = f"https://t.me/{username}"
    try:
        resp = requests.get(url, timeout=10)
        if 'tgme_page_title' in resp.text:
            # Account exists - extract info
            title_match = re.search(r'<div class="tgme_page_title[^"]*"><span[^>]*>([^<]+)', resp.text)
            desc_match = re.search(r'<div class="tgme_page_description[^"]*">([^<]+)', resp.text)
            photo_match = re.search(r'<img class="tgme_page_photo_image" src="([^"]+)"', resp.text)

            return {
                'platform': 'Telegram',
                'username': username,
                'url': url,
                'display_name': title_match.group(1) if title_match else username,
                'bio': desc_match.group(1) if desc_match else '',
                'photo_url': photo_match.group(1) if photo_match else None,
                'exists': True
            }
    except Exception:
        pass
    return {'exists': False}


def check_telegram_usernames(usernames: list) -> list:
    """Check multiple Telegram usernames and return found profiles."""
    results = []
    for username in usernames:
        result = check_telegram_username(username)
        if result.get('exists'):
            results.append(result)
    return results
