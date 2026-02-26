from core.supabase_client import SupabaseClient
c = SupabaseClient()
r = c.client.table('perfiles').select('*').limit(5).execute()
print('count', len(r.data) if r and r.data else 0)
for d in r.data or []:
    print(d)
