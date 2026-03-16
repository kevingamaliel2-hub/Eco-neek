import requests, re, uuid

session = requests.Session()
url = 'http://127.0.0.1:8000/register-screen/'
res = session.get(url, timeout=30)
print('GET', res.status_code)

m = re.search(r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']', res.text)
if not m:
    raise Exception('csrf token not found')
token = m.group(1)
print('csrf', token[:8])

email = f'testcentro_{uuid.uuid4().hex[:8]}@example.com'

data = {
    'csrfmiddlewaretoken': token,
    'tipo': 'centro',
    'responsable': 'Test Resp',
    'nombre_centro': 'Test Centro ' + uuid.uuid4().hex[:6],
    'email': email,
    'password': 'test123456',
    'password2': 'test123456',
    'telefono': '9999999999',
    'direccion': 'Calle 60 #123',
    'municipio': 'Merida',
    'horarios': '8am-6pm',
    'codigo_postal': '97000',
    'estado': 'Yucatan',
    'localidad': 'Merida',
    'colonia': 'Centro',
    'descripcion_publica': 'Test',
    'correo_publico': email,
    'terms': 'on',
    'activo_1': 'on','apertura_1':'08:00','cierre_1':'18:00',
    'activo_2': 'on','apertura_2':'08:00','cierre_2':'18:00',
    'activo_3': 'on','apertura_3':'08:00','cierre_3':'18:00',
    'activo_4': 'on','apertura_4':'08:00','cierre_4':'18:00',
    'activo_5': 'on','apertura_5':'08:00','cierre_5':'18:00',
    'activo_6': 'on','apertura_6':'09:00','cierre_6':'14:00',
    'activo_7': 'on','apertura_7':'09:00','cierre_7':'14:00',
}

# send with headers to mimic browser
headers = {'Referer': url}
resp = session.post(url, data=data, headers=headers, timeout=30)
print('POST', resp.status_code)
print(resp.text[:1400])
