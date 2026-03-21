"""
IBP Structured Logging
======================
Project-wide logging to console + daily rotating log files.
"""

import logging
import os
from datetime import datetime


def setup_logging(log_level='INFO'):
    """Configure IBP logging to console + file."""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f'ibp_{datetime.now().strftime("%Y%m%d")}.log')

    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler (DEBUG level)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler (INFO level)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(formatter)

    # Root IBP logger
    root = logging.getLogger('ibp')
    root.setLevel(logging.DEBUG)
    # Avoid duplicate handlers on reloads
    if not root.handlers:
        root.addHandler(file_handler)
        root.addHandler(console_handler)

    # Also configure app.* loggers to propagate to ibp
    app_logger = logging.getLogger('app')
    app_logger.setLevel(logging.DEBUG)
    if not app_logger.handlers:
        app_logger.addHandler(file_handler)
        app_logger.addHandler(console_handler)

    return root


def mask_token(token):
    """Mask a token for safe logging."""
    if not token:
        return '<not set>'
    return f'...{token[-8:]}' if len(token) > 8 else '****'


def mask_phone(phone):
    """Mask phone number for safe logging."""
    if not phone:
        return '<none>'
    digits = ''.join(c for c in phone if c.isdigit())
    if len(digits) >= 4:
        return f'+7***{digits[-4:]}'
    return '****'


def mask_email(email):
    """Mask email for safe logging."""
    if not email or '@' not in email:
        return '<none>'
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        return f'{local[0]}***@{domain}'
    return f'{local[0]}***{local[-1]}@{domain}'
