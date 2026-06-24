"""Diagnose session/CSRF behavior against local dev server."""
import requests, re, sys

s = requests.Session()

# GET login page
r = s.get('http://127.0.0.1:5000/login')
print('LOGIN GET:', r.status_code, '| cookies:', dict(s.cookies))

# Extract CSRF from form
m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
csrf = m.group(1) if m else ''
print('CSRF:', csrf[:30], '...' if csrf else 'NOT FOUND')

# POST login
r2 = s.post('http://127.0.0.1:5000/login', data={
    'csrf_token': csrf,
    'username': 'Fedor',
    'password': 'vdohnoviteligorborisovichportnoisozdatelfedorigorevichportnoiproductluchshebyratino9',
}, allow_redirects=True)
print('LOGIN POST final URL:', r2.url, '| status:', r2.status_code)
print('cookies after login:', dict(s.cookies))
session_cookie = s.cookies.get('session')
print('session cookie flags (from headers):')
for h in r2.history:
    sc = h.headers.get('Set-Cookie','')
    if 'session' in sc:
        print(' ', sc[:120])

# GET candidate/new
r3 = s.get('http://127.0.0.1:5000/candidate/new')
print('\nCANDIDATE/NEW GET:', r3.status_code, r3.url)
m2 = re.search(r'name="csrf_token" value="([^"]+)"', r3.text)
csrf2 = m2.group(1) if m2 else ''
print('form CSRF:', csrf2[:30])

# POST without pd_consent
r4 = s.post('http://127.0.0.1:5000/candidate/new', data={
    'csrf_token': csrf2,
    'full_name': 'Иванов Петр Сергеевич',
    'date_of_birth': '1985-03-15',
    'phone': '+79161234567',
    'check_mode': 'quick',
}, allow_redirects=False)
print('\nPOST no-consent => status:', r4.status_code, '| Location:', r4.headers.get('Location',''))

# POST with pd_consent
r5 = s.post('http://127.0.0.1:5000/candidate/new', data={
    'csrf_token': csrf2,
    'full_name': 'Иванов Петр Сергеевич',
    'date_of_birth': '1985-03-15',
    'phone': '+79161234567',
    'check_mode': 'quick',
    'pd_consent': 'true',
}, allow_redirects=False)
print('POST with-consent => status:', r5.status_code, '| Location:', r5.headers.get('Location',''))
if r5.status_code == 200:
    # Validation error - show the error message
    errs = re.findall(r'class="[^"]*error[^"]*"[^>]*>([^<]+)<', r5.text)
    print('  validation errors:', errs)
