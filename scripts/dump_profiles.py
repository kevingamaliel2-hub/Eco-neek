from core.supabase_client import SupabaseClient

c = SupabaseClient()
resp = c.client.table('perfiles').select('*').limit(5).execute()
print('count', len(resp.data) if resp and resp.data else 0)
for d in resp.data or []:
    print(d)
