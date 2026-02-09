"""
Holehe Email Verification Service
=================================
Checks if an email is registered on 120+ services.
100% FREE, open-source.

Key feature: Target is NOT notified (no password reset email sent)

Based on: https://github.com/megadose/holehe
"""

import asyncio
import subprocess
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Try to import holehe
HOLEHE_AVAILABLE = False
try:
    import httpx
    HOLEHE_AVAILABLE = True
except ImportError:
    logger.warning("httpx not installed. Holehe will use CLI fallback.")


@dataclass
class EmailRegistration:
    """Information about email registration on a service."""
    service: str
    exists: bool
    email_recovery: Optional[str] = None  # Masked recovery email if available
    phone_recovery: Optional[str] = None  # Masked recovery phone if available
    profile_url: Optional[str] = None
    extra_info: Dict = field(default_factory=dict)


@dataclass
class HoleheResults:
    """Results of Holehe email check."""
    email: str
    registered_services: List[EmailRegistration] = field(default_factory=list)
    total_checked: int = 0
    total_registered: int = 0
    error: Optional[str] = None


async def check_email_holehe_async(email: str) -> HoleheResults:
    """
    Check which services an email is registered on using holehe library.

    Args:
        email: Email address to check

    Returns:
        HoleheResults with list of registered services
    """
    registered = []
    total_checked = 0

    try:
        # Import holehe modules dynamically
        import holehe.modules as modules
        import pkgutil

        # Get all module names
        module_list = []
        for importer, modname, ispkg in pkgutil.iter_modules(modules.__path__):
            if not ispkg:
                module_list.append(modname)

        # Create async client
        async with httpx.AsyncClient(timeout=15.0) as client:
            out = []

            # Run checks for each module
            for module_name in module_list:
                try:
                    module = __import__(f'holehe.modules.{module_name}', fromlist=[module_name])
                    if hasattr(module, module_name):
                        check_func = getattr(module, module_name)
                        await check_func(email, client, out)
                        total_checked += 1
                except Exception as e:
                    logger.debug(f"Holehe module {module_name} error: {e}")
                    continue

            # Parse results
            for result in out:
                if result.get('exists'):
                    registered.append(EmailRegistration(
                        service=result.get('name', 'Unknown'),
                        exists=True,
                        email_recovery=result.get('emailrecovery'),
                        phone_recovery=result.get('phoneNumber'),
                        profile_url=result.get('profileurl'),
                        extra_info={
                            k: v for k, v in result.items()
                            if k not in ('name', 'exists', 'emailrecovery', 'phoneNumber', 'profileurl')
                        }
                    ))

    except ImportError:
        logger.warning("Holehe library not installed. Using CLI fallback.")
        return check_email_cli(email)
    except Exception as e:
        logger.error(f"Holehe async error: {e}")
        return HoleheResults(
            email=email,
            registered_services=[],
            total_checked=0,
            total_registered=0,
            error=str(e)
        )

    return HoleheResults(
        email=email,
        registered_services=registered,
        total_checked=total_checked,
        total_registered=len(registered)
    )


def check_email_sync(email: str) -> HoleheResults:
    """
    Synchronous wrapper - uses CLI directly since async module loading is broken.

    Args:
        email: Email address to check

    Returns:
        HoleheResults with list of registered services
    """
    # Use CLI directly - async version has broken module loading due to nested directories
    logger.info(f"Checking email with Holehe CLI: {email}")
    return check_email_cli(email)


def check_email_cli(email: str) -> HoleheResults:
    """
    Fallback: Run holehe via CLI.

    Args:
        email: Email address to check

    Returns:
        HoleheResults with list of registered services
    """
    registered = []

    try:
        # Run holehe CLI command with short timeout
        result = subprocess.run(
            ['holehe', email, '--only-used', '--no-color', '--no-clear', '-T', '5'],
            capture_output=True,
            text=True,
            timeout=15,  # 15 second timeout
            encoding='utf-8',
            errors='replace'
        )

        # Parse output
        logger.debug(f"Holehe raw output for {email}:\n{result.stdout[:1000]}")

        for line in result.stdout.split('\n'):
            line = line.strip()
            # Skip empty lines and progress bars
            if not line or '|' in line or line.startswith('Twitter') or line.startswith('Github'):
                continue
            if '[+]' in line:
                # Extract service name (format: [+] servicename)
                parts = line.split('[+]')
                if len(parts) > 1:
                    service_part = parts[1].strip()
                    # Get service name (before colon or space)
                    service = service_part.split(':')[0].split()[0] if service_part else 'Unknown'
                    service = service.strip()
                    if service and service.lower() not in ('email', 'used'):
                        logger.info(f"Holehe found: {email} -> {service}")
                        registered.append(EmailRegistration(
                            service=service,
                            exists=True
                        ))

        return HoleheResults(
            email=email,
            registered_services=registered,
            total_checked=120,  # Approximate number of services holehe checks
            total_registered=len(registered)
        )

    except subprocess.TimeoutExpired:
        logger.error(f"Holehe CLI timeout for {email}")
        return HoleheResults(
            email=email,
            registered_services=[],
            total_checked=0,
            total_registered=0,
            error="Timeout"
        )
    except FileNotFoundError:
        logger.error("Holehe CLI not found. Install with: pip install holehe")
        return HoleheResults(
            email=email,
            registered_services=[],
            total_checked=0,
            total_registered=0,
            error="Holehe not installed"
        )
    except Exception as e:
        logger.error(f"Holehe CLI error: {e}")
        return HoleheResults(
            email=email,
            registered_services=[],
            total_checked=0,
            total_registered=0,
            error=str(e)
        )


async def batch_check_emails_async(
    emails: List[str],
    delay: float = 1.0
) -> Dict[str, HoleheResults]:
    """
    Check multiple emails with rate limiting (async version).

    Args:
        emails: List of emails to check
        delay: Seconds between checks (default 1.0 to avoid rate limits)

    Returns:
        Dict mapping email to results
    """
    results = {}

    for email in emails:
        results[email] = await check_email_holehe_async(email)
        await asyncio.sleep(delay)  # Rate limiting

    return results


def batch_check_emails(
    emails: List[str],
    delay: float = 1.0
) -> Dict[str, HoleheResults]:
    """
    Check multiple emails with rate limiting (sync version).

    Args:
        emails: List of emails to check
        delay: Seconds between checks

    Returns:
        Dict mapping email to results
    """
    import time
    results = {}

    for email in emails:
        results[email] = check_email_sync(email)
        time.sleep(delay)

    return results


def get_service_categories() -> Dict[str, List[str]]:
    """
    Get categories of services that holehe checks.

    Returns:
        Dict mapping category name to list of service names
    """
    return {
        'social': [
            'instagram', 'twitter', 'facebook', 'tiktok', 'pinterest',
            'reddit', 'tumblr', 'quora', 'discord'
        ],
        'shopping': [
            'amazon', 'ebay', 'aliexpress', 'etsy', 'wish'
        ],
        'streaming': [
            'spotify', 'netflix', 'disney', 'hulu', 'twitch'
        ],
        'gaming': [
            'steam', 'origin', 'uplay', 'epic', 'riot'
        ],
        'email': [
            'gmail', 'yahoo', 'outlook', 'protonmail'
        ],
        'dating': [
            'tinder', 'bumble', 'badoo', 'okcupid'
        ],
        'work': [
            'linkedin', 'github', 'gitlab', 'bitbucket', 'slack'
        ],
        'russian': [
            'vk', 'mail.ru', 'yandex', 'ok.ru'
        ]
    }
