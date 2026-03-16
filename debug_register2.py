import requests, re, uuid
s=requests.Session()
u='http://127.0.0.1:8000/register-screen/'
r=s.get(u, timeout=30)
print('GET', r.status_code)
m = re.search(r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']', r.text)
if not m:
    raise SystemExit('csrf missing')
t=m.group(1)

data={'csrfmiddlewaretoken':t,
      'tipo':'centro',
      'responsable':'Test',
      'nombre_centro':'Test'+uuid.uuid4().hex[:6],
      'email':'test'+uuid.uuid4().hex[:6]+'@example.com',
      'password':'test123456',
      'password2':'test123456',
      'telefono':'9999999999',
      'direccion':'Calle X 123',
      'municipio':'Merida',
      'horarios':'8-18',
      'codigo_postal':'97000',
      'estado':'Yucatan',
      'localidad':'Merida',
      'colonia':'Centro',
      'descripcion_publica':'Test',
      'correo_publico':'test@test.com',
      'terms':'on',
      'activo_1':'on','apertura_1':'08:00','cierre_1':'18:00'}

r2=s.post(u, data=data, headers={'Referer':u}, timeout=30)
print('POST', r2.status_code)
print('url', r2.url)
print('error text found', 'No se pudo crear el centro' in r2.text)
print('centro_pendiente', 'centro_pendiente' in r2.text)
print('len', len(r2.text))
print(r2.text[0:1200])
