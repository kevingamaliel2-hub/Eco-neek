from core.supabase_client import SupabaseClient
import requests

s = SupabaseClient()
email = 'testuser1@example.com'
password = 'Secret123!'
print('creating', email)
resp = requests.post(f'{s.url}/auth/v1/signup', headers=s.headers, json={'email': email, 'password': password})
print(resp.status_code, resp.text)
resp2 = s.sign_in(email, password)
print('signin', getattr(resp2, 'error', None), getattr(resp2, 'data', None) and list(resp2.data.keys()))
