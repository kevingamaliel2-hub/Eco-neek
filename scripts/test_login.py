import requests
import re

url = 'http://127.0.0.1:8000/login-screen/'
s = requests.Session()
resp = s.get(url)
# regex to extract csrfmiddlewaretoken value
m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', resp.text)
csrftoken = m.group(1) if m else None
print('csrf', csrftoken)
data = {'login': 'testuser1@example.com', 'password': 'Secret123!', 'csrfmiddlewaretoken': csrftoken}
resp2 = s.post(url, data=data, allow_redirects=False)
print('post status', resp2.status_code, resp2.headers.get('location'))
print('cookies', s.cookies.get_dict())
