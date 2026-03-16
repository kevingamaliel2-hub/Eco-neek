import requests
import re

s = requests.Session()
r = s.get('http://127.0.0.1:8000/login-screen/')
print('GET login', r.status_code)
if r.status_code != 200:
    print(r.text[:600])
    raise SystemExit(1)

m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text)
print('csrf found', bool(m))
if not m:
    print('no csrf')
    raise SystemExit(1)

tok = m.group(1)
print('tok prefix', tok[:12])

p = s.post('http://127.0.0.1:8000/login-screen/',
           data={'csrfmiddlewaretoken': tok, 'login': 'admin@test.com', 'password': '123456'},
           headers={'Referer': 'http://127.0.0.1:8000/login-screen/'},
           allow_redirects=False)
print('POST login', p.status_code, p.headers.get('Location'))
print('POST body len', len(p.text))
if p.status_code in (301,302,303,307):
    target = p.headers.get('Location')
    print('→ redirect', target)
    if target.startswith('/'):
        q = s.get('http://127.0.0.1:8000' + target)
        print('redirect page', q.status_code)
        print(q.text[:800])
else:
    print(p.text[:800])

q = s.get('http://127.0.0.1:8000/panel/centros/', allow_redirects=False)
print('panel', q.status_code, q.headers.get('Location'))
print(q.text[:800])
