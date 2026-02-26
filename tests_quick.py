import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

django.setup()

from django.test import Client

c = Client()

print('GET /api/ ->', c.get('/api/').status_code)

reg = c.post('/api/auth/register/', {'username': 'apitest', 'email': 'apitest@example.com', 'password': 'testpass'})
print('POST /api/auth/register/ ->', reg.status_code, reg.content.decode()[:1000])

tok = c.post('/api/auth/token/', {'username': 'apitest', 'password': 'testpass'})
print('POST /api/auth/token/ ->', tok.status_code, tok.content.decode()[:1000])

if tok.status_code == 200:
    access = json.loads(tok.content)['access']
    c.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + access
    centro_data = json.dumps({'name': 'Centro Test', 'address': 'Direccion prueba'})
    r = c.post('/api/centros/', centro_data, content_type='application/json')
    print('POST /api/centros/ ->', r.status_code, r.content.decode()[:1000])
else:
    print('Token request failed')
