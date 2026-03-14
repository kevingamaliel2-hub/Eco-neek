# Despliegue Django + Gunicorn + Nginx (Google Cloud)

Esta guía cubre el proceso completo de despliegue en una instancia Linux (Ubuntu), con Gunicorn + Nginx + HTTPS + dominio.

## 1) Preparación de la instancia (Google Cloud)

1. Abre Google Cloud Console → Compute Engine → VM instances → Create instance.
2. Elige Ubuntu 22.04 LTS.
3. En Firewall, habilita HTTP y HTTPS.
4. Crea la VM y copia la IP externa.

**Notas:**
- La IP externa será la dirección de tu servidor.
- En Hostinger dirigirás tu dominio a esta IP (registro A).

## 2) DNS (Hostinger) y Google API

### Hostinger
- En DNS, agrega registro A:
  - `@` → IP externa
  - `www` → IP externa
- Espera propagación DNS (10-30 min).

### Google API (si usas Google OAuth / Maps)
- Agrega orígenes permitidos:
  - `https://tudominio.com`
- Agrega URI de redireccionamiento autorizados (OAuth):
  - `https://tudominio.com/accounts/google/login/callback/`

## 3) Instalar dependencias en la VM

En la VM (SSH):

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip nginx git curl
```

## 4) Clonar el proyecto y crear entorno virtual

```bash
cd /opt
sudo mkdir -p /opt/ecoloop
sudo chown $USER:$USER /opt/ecoloop
cd /opt/ecoloop
git clone <url-del-repo> .
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

## 5) Configurar variables de entorno

Crea archivo `backend/.env`:

```ini
DJANGO_SECRET_KEY=<tu-secret>
DEBUG=False
ALLOWED_HOSTS=127.0.0.1,<tu-ip>,tudominio.com
DATABASE_URL=<tu_database_url>
SUPABASE_URL=<tu_supabase_url>
SUPABASE_ANON_KEY=<tu_supabase_key>
```

Asegúrate de que el archivo está ignorado por Git (`.gitignore` incluye `backend/.env`).

## 6) Ajustes seguros de Django

En `backend/settings.py`:
- `DEBUG = os.getenv('DEBUG', 'False') == 'True'`
- `ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')`
- Agregar configuraciones de seguridad:

```python
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
```

Y CORS:

```python
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = ['https://tudominio.com']
```

## 7) Migraciones y archivos estáticos

```bash
cd /opt/ecoloop/backend
source /opt/ecoloop/.venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## 8) Probar Gunicorn localmente

```bash
gunicorn backend.wsgi:application --bind 127.0.0.1:8000
```

Abrir `http://<tu-ip>:8000` para verificar.

## 9) Crear service systemd para Gunicorn

Crea `/etc/systemd/system/ecoleek.service` con:

```ini
[Unit]
Description=Gunicorn EcoNeek app
After=network.target

[Service]
User=<tu-usuario>
Group=www-data
WorkingDirectory=/opt/ecoloop/backend
EnvironmentFile=/opt/ecoloop/backend/.env
ExecStart=/opt/ecoloop/.venv/bin/gunicorn backend.wsgi:application \
    --workers 3 \
    --bind 127.0.0.1:8000 \
    --log-level info

[Install]
WantedBy=multi-user.target
```

Activar el servicio:

```bash
sudo systemctl daemon-reload
sudo systemctl start ecoleek
sudo systemctl enable ecoleek
sudo systemctl status ecoleek
```

## 10) Configurar Nginx

Crea `/etc/nginx/sites-available/ecoloop`:

```nginx
server {
    listen 80;
    server_name tudominio.com www.tudominio.com <tu-ip>;

    location /static/ {
        alias /opt/ecoloop/backend/static/;
    }

    location /media/ {
        alias /opt/ecoloop/backend/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Habilitar Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/ecoloop /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

Verifica `http://<tu-ip>` y `http://tudominio.com`.

## 11) SSL con Let’s Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d tudominio.com -d www.tudominio.com
```

Verifica el certificado:

```bash
sudo systemctl status certbot.timer
```

## 12) Verificación final

- `curl -I https://tudominio.com` debe devolver 200.
- `sudo systemctl status ecoleek`
- `sudo systemctl status nginx`
- Prueba flujo login/perfil/canjes/qr.

## 13) Notas de seguridad

- Nunca dejes `DEBUG=True` en producción.
- Revisa que no haya datos sensibles en logs (p.ej. `login_debug.log`).
- Elimina endpoints debug (`/debug/...`) antes de producción.
- Revisa permisos de API y no expongas service_role keys en frontend.

## 14) Mantenimiento

- Renovación SSL automática con certbot.
- Reiniciar servidor tras cambios:
  - `sudo systemctl restart ecoleek`
  - `sudo systemctl restart nginx`
- Actualizar código:
  - `git pull origin main`
  - `pip install -r requirements.txt`
  - `python manage.py migrate`
  - `python manage.py collectstatic --noinput`
  - reiniciar servicios
