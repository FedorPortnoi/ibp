import logging

logger = logging.getLogger(__name__)


def sanitize_username(username: str) -> str:
    """Strip path-traversal and shell-dangerous chars from a username.

    Returns the cleaned username, or '' if it becomes too short to be valid.
    """
    username = username.strip()
    username = username.replace('/', '').replace('\\', '').replace('\0', '')
    username = username.replace('..', '').replace('~', '')
    if len(username) < 2:
        logger.warning("Username rejected after sanitization")
        return ''
    return username
