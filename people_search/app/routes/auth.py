import os
from functools import wraps
from flask import Blueprint, render_template, request, redirect, session, url_for

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        pwd = os.environ.get('IBP_PASSWORD', '')
        if pwd and not session.get('authenticated'):
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == os.environ.get('IBP_PASSWORD', ''):
            session['authenticated'] = True
            return redirect(url_for('search.index'))
        error = 'Неверный пароль'
    return render_template('login.html', error=error)


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
