"""
Subscription routes for IBP.
Payment is handled by YooKassa.  The stub activation path (IBP_STUB_PAYMENTS=true)
is available in development only and is blocked in production.
"""

import os
import logging
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, current_app
)

from app import db
from app.models.subscription import Subscription
from app.models.user import User
from app.routes.auth import get_current_user, login_required
from app.services.email_service import send_subscription_confirmation

logger = logging.getLogger('ibp.subscribe')

subscribe_bp = Blueprint('subscribe', __name__)

PRICE_RUB = 1500
PERIOD_DAYS = 30


@subscribe_bp.route('/subscribe', methods=['GET'])
@login_required
def subscribe_page():
    user = get_current_user()

    # Admin bypasses subscription
    if user.is_admin:
        return redirect(url_for('candidate.new_check'))

    # Already active subscription
    sub = Subscription.query.filter_by(user_id=user.id).first()
    if sub and sub.is_active:
        return redirect(url_for('candidate.new_check'))

    return render_template('subscribe.html', user=user,
                           price=PRICE_RUB, days=PERIOD_DAYS)


@subscribe_bp.route('/subscribe/pay', methods=['POST'])
@login_required
def pay():
    """
    Payment handler.

    Production: initiate a real YooKassa payment and redirect the user to the
    payment page.  The subscription is activated only after YooKassa calls back
    the /subscribe/webhook endpoint with a verified success status.

    Development (IBP_STUB_PAYMENTS=true only): activate immediately so the
    subscription flow can be tested without a live payment processor.
    This path is hard-blocked unless the env var is explicitly set.
    """
    # Block stub activation in production — requires explicit opt-in.
    stub_allowed = os.environ.get('IBP_STUB_PAYMENTS', '').lower() in ('1', 'true', 'yes')
    if not stub_allowed:
        logger.warning("Stub payment attempt blocked (IBP_STUB_PAYMENTS not set)")
        return render_template('subscribe.html',
                               user=get_current_user(),
                               price=PRICE_RUB,
                               days=PERIOD_DAYS,
                               error='Онлайн-оплата временно недоступна. Свяжитесь с поддержкой.'), 503

    user = get_current_user()
    auto_renew = request.form.get('auto_renew') == 'on'
    email = request.form.get('email', '').strip() or None

    if user.is_admin:
        return redirect(url_for('candidate.new_check'))

    # Save email to user if provided
    if email and not user.email:
        user.email = email

    # Create or update subscription
    sub = Subscription.query.filter_by(user_id=user.id).first()
    if not sub:
        sub = Subscription(user_id=user.id)
        db.session.add(sub)

    sub.activate(payment_id=f'stub_{user.id}', auto_renew=auto_renew)
    db.session.commit()

    logger.info(f"Subscription activated for user '{user.username}' (stub payment, dev only)")
    from app import audit
    audit.log('subscription.activate', user_id=user.id,
              target_type='Subscription', target_id=str(sub.id),
              metadata={'payment_id': sub.payment_id, 'expires_at': str(sub.expires_at)})

    target_email = email or user.email
    if target_email:
        send_subscription_confirmation(
            username=user.username,
            email=target_email,
            expires_at=sub.expires_at,
            auto_renew=auto_renew,
        )

    return redirect(url_for('subscribe.success'))


@subscribe_bp.route('/subscribe/success')
@login_required
def success():
    user = get_current_user()
    sub = Subscription.query.filter_by(user_id=user.id).first()
    return render_template('subscribe_success.html', user=user, sub=sub)


@subscribe_bp.route('/subscribe/status')
@login_required
def status():
    user = get_current_user()
    sub = Subscription.query.filter_by(user_id=user.id).first()
    return render_template('subscribe_status.html', user=user, sub=sub)
