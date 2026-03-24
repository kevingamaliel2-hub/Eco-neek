# backend/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,econeek.com,136.113.230.27').split(',')

# In development, optionally accept NGROK_HOST for local testing.
if DEBUG:
    ngrok_host = os.getenv('NGROK_HOST')
    if ngrok_host and ngrok_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(ngrok_host)

    try:
        import requests
        resp = requests.get('http://127.0.0.1:4040/api/tunnels', timeout=0.5)
        data = resp.json()
        for t in data.get('tunnels', []):
            public = t.get('public_url', '')
            if public:
                host = public.replace('http://', '').replace('https://', '')
                if host not in ALLOWED_HOSTS:
                    ALLOWED_HOSTS.append(host)
    except Exception:
        pass

# Trust headers when behind a proxy (load balancer, reverse proxy)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    
    # Third party
    'django_otp',  # Base para OTP
    'django_otp.plugins.otp_totp',  # TOTP (Google Authenticator)
    'two_factor',  # Librería principal 2FA (debe ir antes de allauth)
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_extensions',  # Para runserver_plus con HTTPS local
    
    # Local
    'core.apps.CoreConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    # 'core.middleware.TwoFactorMiddleware',  # Fuerza 2FA en staff (temporalmente deshabilitado)
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Try to add Flutter images if they exist (works on any OS)
# Flutter project location relative to this backend
_flutter_base = BASE_DIR.parent.parent / 'ecoloop_flutter'
_flutter_images = _flutter_base / 'assets' / 'images'
if _flutter_images.exists():
    STATICFILES_DIRS.append(_flutter_images)

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Limitar tamaño de subida a nivel de Django (previene que un upload de 50MB caiga el servidor)
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024   # 2 MB total por request
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024   # 2 MB por archivo

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# ...todo lo anterior igual...

SITE_ID = 1

# Provider specific settings
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': False,
    }
}

# Login/Logout settings
LOGIN_REDIRECT_URL = '/completar-registro/'
LOGOUT_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_ON_GET = True
SOCIALACCOUNT_LOGIN_ON_GET = True

# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # En prod use un backend real (SMTP, SendGrid, etc.)
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'  # Mejora de seguridad: verificar correo antes de acceder.
ACCOUNT_LOGIN_METHODS = {'username', 'email'}
# ACCOUNT_AUTHENTICATION_METHOD = 'username_email'  # Deprecated en Django-allauth 5.2
# ACCOUNT_USER_MODEL_USERNAME_FIELD = 'username'  # asume el UserModel actual
# ACCOUNT_USERNAME_REQUIRED = True  # Deprecated, usa ACCOUNT_SIGNUP_FIELDS
# ACCOUNT_EMAIL_REQUIRED = True  # Deprecated, usa ACCOUNT_SIGNUP_FIELDS
ACCOUNT_PASSWORD_MIN_LENGTH = 12

# OTP/MFA: configuración para django-two-factor-auth
# LOGIN_URL = 'two_factor:login'  # Redirige login a 2FA si está configurado
# ACCOUNT_ADAPTER = 'two_factor.adapters.TwoFactorAdapter'  # Integra con allauth
LOGIN_REDIRECT_URL = '/'  # Redirige después del login exitoso
TWO_FACTOR_PATCH_ADMIN = True  # Protege admin con 2FA si está configurado
TWO_FACTOR_QR_FACTORY = 'qrcode.image.pil.PilImage'  # Para generar QR
TWO_FACTOR_LOGIN_TIMEOUT = 600  # 10 min timeout para login 2FA

# OTP/MFA: instalar django-two-factor-auth y django-otp para activar completamente
# (no está en requirements por defecto). En producción, añadir:
# INSTALLED_APPS += ['django_otp', 'django_otp.plugins.otp_totp', 'two_factor']
# y usar two_factor.urls para rutas /account/login/ etc.

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://nzywjcjferkjmuxhuznm.supabase.co')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': '200/day',
        'user': '1000/day',
    },
}

# CORS
CORS_ALLOWED_ORIGINS = [
    'https://econeek.com',
    'https://www.econeek.com',
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]
CORS_ALLOWED_ORIGIN_REGEXES = [r'^https://.*\.econeek\.com$']

# Production security
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG and os.getenv('SECURE_SSL_REDIRECT', 'True') == 'True'
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000')) if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Duración y seguridad de sesiones
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 7 días
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # usual en Django; con secure+sameSite definido
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'

# Logging básico local/producción
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'django.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

# Al final del archivo, después de todas las configuraciones
AUTH_USER_MODEL = 'core.UsuarioDjango'