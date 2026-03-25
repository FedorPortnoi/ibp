"""
Email Service
=============
Send transactional emails via Resend API.
Graceful fallback: if RESEND_API_KEY is unset, logs warning and returns False.
"""

import logging
import os

import requests

logger = logging.getLogger('ibp.email')

RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
FROM_EMAIL = 'noreply@shtirletzsled.ru'
RESEND_URL = 'https://api.resend.com/emails'


def send_email(to: str, subject: str, html: str) -> bool:
    """Send email via Resend. Returns True if sent successfully."""
    if not RESEND_API_KEY:
        logger.warning(f"RESEND_API_KEY not set — email to {to} not sent")
        return False

    try:
        resp = requests.post(
            RESEND_URL,
            headers={
                'Authorization': f'Bearer {RESEND_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'from': FROM_EMAIL,
                'to': [to],
                'subject': subject,
                'html': html,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info(f"Email sent to {to}: {subject}")
            return True
        else:
            logger.error(f"Resend error {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


def send_subscription_confirmation(username: str, email: str,
                                   expires_at, auto_renew: bool) -> bool:
    """Send subscription confirmation email."""
    expires_str = expires_at.strftime('%d.%m.%Y')
    auto_renew_str = 'включено' if auto_renew else 'отключено'

    html = f"""<!DOCTYPE html>
<html>
<body style="background:#1C1C1C;color:#ECECEC;font-family:Inter,sans-serif;
             padding:40px;max-width:480px;margin:0 auto;">
    <h1 style="font-size:20px;font-weight:300;letter-spacing:.2em;
               text-transform:uppercase;color:#ECECEC;">ШТИРЛИЦ</h1>
    <p style="color:#9B9B9B;font-size:12px;letter-spacing:.1em;
              text-transform:uppercase;margin-bottom:32px;">
        OSINT &middot; Россия и СНГ
    </p>

    <h2 style="font-size:16px;font-weight:400;color:#D4A27F;margin-bottom:16px;">
        Подписка активирована
    </h2>

    <p style="color:#ECECEC;font-size:14px;line-height:1.8;">
        Привет, <strong>{username}</strong>!<br><br>
        Ваша подписка на ШТИРЛИЦ успешно активирована.
    </p>

    <div style="background:#262626;border:1px solid #383838;
                padding:20px 24px;margin:24px 0;border-radius:4px;">
        <table style="width:100%;border-collapse:collapse;">
            <tr>
                <td style="color:#9B9B9B;font-size:12px;padding:6px 0;">Тариф</td>
                <td style="color:#ECECEC;font-size:12px;padding:6px 0;text-align:right;">1 500 &#8381; / месяц</td>
            </tr>
            <tr>
                <td style="color:#9B9B9B;font-size:12px;padding:6px 0;">Действует до</td>
                <td style="color:#ECECEC;font-size:12px;padding:6px 0;text-align:right;">{expires_str}</td>
            </tr>
            <tr>
                <td style="color:#9B9B9B;font-size:12px;padding:6px 0;">Авторенью</td>
                <td style="color:#ECECEC;font-size:12px;padding:6px 0;text-align:right;">{auto_renew_str}</td>
            </tr>
        </table>
    </div>

    <a href="https://shtirletzsled.ru/candidate/new"
       style="display:inline-block;background:#D4A27F;color:#000;
              padding:12px 28px;text-decoration:none;font-size:11px;
              font-weight:500;letter-spacing:.15em;text-transform:uppercase;
              margin-bottom:32px;">
        Перейти к ШТИРЛИЦ &rarr;
    </a>

    <p style="color:#6B6B6B;font-size:11px;line-height:1.6;">
        Если у вас есть вопросы &mdash; ответьте на это письмо.<br>
        ШТИРЛИЦ &middot; OSINT Platform
    </p>
</body>
</html>"""

    return send_email(to=email, subject='Подписка ШТИРЛИЦ активирована', html=html)
