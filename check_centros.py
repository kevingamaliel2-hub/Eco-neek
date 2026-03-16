from core.supabase_client import SupabaseClient
s=SupabaseClient()
resp=s.client.table('centros_acopio').select('*').order('created_at', desc=True).limit(5).execute()
print('error', getattr(resp, 'error', None))
print('data', getattr(resp, 'data', None))
