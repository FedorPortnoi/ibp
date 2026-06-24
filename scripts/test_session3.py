"""Check Set-Cookie headers and session validity."""
import requests, base64, json, re

s = requests.Session()
r = s.get('http://127.0.0.1:5000/login')

# Print all Set-Cookie headers
print('=== Set-Cookie headers ===')
for k, v in r.headers.items():
    if k.lower() == 'set-cookie':
        print('  ', v)

# Decode session cookie
sc = s.cookies.get('session', '')
if sc:
    parts = sc.split('.')
    payload_b64 = parts[0]
    # Add padding
    payload_b64 += '=' * (4 - len(payload_b64) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload_b64)
        print('\nSession payload:', decoded.decode())
    except Exception as e:
        print('Could not decode session:', e)

# Check if cookie was actually sent on POST
print('\n=== Testing POST with explicit cookie header ===')
m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
csrf = m.group(1) if m else ''
r2 = requests.post('http://127.0.0.1:5000/login',
    data={'csrf_token': csrf, 'username': 'Fedor',
          'password': 'vdohnoviteligorborisovichportnoisozdatelfedorigorevichportnoiproductluchshebyratino9'},
    headers={'Cookie': f'session={sc}'},
    allow_redirects=False)
print('Status:', r2.status_code, '| Location:', r2.headers.get('Location',''))
if r2.status_code >= 400:
    print('Error:', r2.text[:200])

# Check config via a debug endpoint if it exists
print('\n=== Testing /health ===')
r3 = requests.get('http://127.0.0.1:5000/health')
print(r3.text[:200])
