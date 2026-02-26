import os
from django.conf import settings
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','backend.settings')
django.setup()
print('SUPABASE_URL', getattr(settings,'SUPABASE_URL',None))
from core.supabase_client import SupabaseClient
print('creating instance')
try:
    SupabaseClient()
    print('constructed successfully')
except Exception as e:
    print('exception constructing', repr(e))
