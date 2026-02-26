# Econeek (Django backend)

This folder contains a minimal Django project scaffold to start migrating the PHP app.

Quick start (Windows PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# create a .env with DATABASE_URL, SECRET_KEY, GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET
setx DATABASE_URL "your_database_url"
setx SECRET_KEY "your_secret_key"
# run migrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Next steps I can do for you:
- Configure Supabase connection in settings using your DATABASE_URL
- Add `django-allauth` Google provider credentials and test OAuth callback
- Design Django models mapping from your PHP models
