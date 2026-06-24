"""Diagnose 400 on login POST."""
import requests, re

s = requests.Session()
r = s.get('http://127.0.0.1:5000/login')
print('GET cookies:', dict(s.cookies))

m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
csrf = m.group(1) if m else ''
print('csrf from form:', repr(csrf[:40]))

# Check if there's also a meta csrf-token
m2 = re.search(r'name="csrf-token" content="([^"]+)"', r.text)
meta_csrf = m2.group(1) if m2 else ''
print('csrf from meta:', repr(meta_csrf[:40]))

# Try login POST
r2 = s.post('http://127.0.0.1:5000/login', data={
    'csrf_token': csrf,
    'username': 'Fedor',
    'password': 'vdohnoviteligorborisovichportnoisozdatelfedorigorevichportnoiproductluchshebyratino9',
}, allow_redirects=False)
print('Login POST status:', r2.status_code)
print('Location header:', r2.headers.get('Location', ''))
if r2.status_code >= 400:
    # Print first 500 chars of response to see the error
    body = r2.text[:500]
    print('Response body snippet:', body)

# Also test with explicit referer (some CSRF impls check it)
s2 = requests.Session()
r3 = s2.get('http://127.0.0.1:5000/login')
m3 = re.search(r'name="csrf_token" value="([^"]+)"', r3.text)
csrf3 = m3.group(1) if m3 else ''
r4 = s2.post('http://127.0.0.1:5000/login',
    data={'csrf_token': csrf3, 'username': 'Fedor',
          'password': 'vdohnoviteligorborisovichportnoisozdatelfedorigorevichportnoiproductluchshebyratino9'},
    headers={'Referer': 'http://127.0.0.1:5000/login'},
    allow_redirects=False)
print('\nWith Referer header - status:', r4.status_code, '| Location:', r4.headers.get('Location',''))
if r4.status_code == 302:
    print('cookies after login:', dict(s2.cookies))
    # try candidate/new
    r5 = s2.get('http://127.0.0.1:5000/candidate/new')
    print('candidate/new GET:', r5.status_code, r5.url)
