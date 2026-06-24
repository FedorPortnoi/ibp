"""User profile — view account info and change password."""

from flask import Blueprint, render_template, request, redirect, url_for

from app import db
from app.routes.auth import login_required, get_current_user

profile_bp = Blueprint('profile', __name__, url_prefix='/profile')


@profile_bp.route('/', methods=['GET', 'POST'])
@login_required
def profile():
    user = get_current_user()
    error = None
    success = None

    if request.method == 'POST':
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')

        if not user.check_password(current_pw):
            error = 'Неверный текущий пароль'
        elif len(new_pw) < 8:
            error = 'Новый пароль должен быть не короче 8 символов'
        elif new_pw != confirm_pw:
            error = 'Пароли не совпадают'
        else:
            user.set_password(new_pw)
            db.session.commit()
            success = 'Пароль успешно изменён'

    return render_template('profile.html', user=user, error=error, success=success)
