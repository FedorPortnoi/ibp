"""
Gravatar Lookup Service
=======================
Checks if email has a Gravatar profile and extracts data.
100% FREE, no limits.
"""

import hashlib
import requests
from typing import Optional, Dict, List
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class GravatarProfile:
    """Container for Gravatar profile information."""
    exists: bool
    email: str = ""
    display_name: Optional[str] = None
    profile_url: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    websites: List[str] = field(default_factory=list)
    accounts: List[Dict[str, str]] = field(default_factory=list)  # Linked social accounts


def check_gravatar(email: str) -> GravatarProfile:
    """
    Check if email has a Gravatar profile.

    Args:
        email: Email address to check

    Returns:
        GravatarProfile with available data
    """
    email = email.lower().strip()

    # Create MD5 hash of email
    email_hash = hashlib.md5(email.encode(), usedforsecurity=False).hexdigest()

    # Check profile JSON endpoint
    profile_url = f"https://gravatar.com/{email_hash}.json"

    try:
        response = requests.get(profile_url, timeout=10)

        if response.status_code == 404:
            # No Gravatar profile for this email
            return GravatarProfile(exists=False, email=email)

        if response.status_code == 200:
            data = response.json()
            entry = data.get('entry', [{}])[0]

            # Extract linked accounts
            accounts = []
            for account in entry.get('accounts', []):
                accounts.append({
                    'domain': account.get('domain', ''),
                    'username': account.get('username', ''),
                    'url': account.get('url', ''),
                    'display': account.get('display', '')
                })

            # Extract websites/URLs
            websites = [u.get('value', '') for u in entry.get('urls', []) if u.get('value')]

            return GravatarProfile(
                exists=True,
                email=email,
                display_name=entry.get('displayName'),
                profile_url=entry.get('profileUrl'),
                avatar_url=f"https://gravatar.com/avatar/{email_hash}?s=400",
                bio=entry.get('aboutMe'),
                location=entry.get('currentLocation'),
                websites=websites,
                accounts=accounts
            )

    except requests.exceptions.Timeout:
        logger.warning(f"Gravatar timeout for {email}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Gravatar error for {email}: {e}")
    except (ValueError, KeyError) as e:
        logger.warning(f"Gravatar parse error for {email}: {e}")

    return GravatarProfile(exists=False, email=email)


