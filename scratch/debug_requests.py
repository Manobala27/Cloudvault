import urllib.request
import urllib.parse
import http.cookiejar
import re

def test_request():
    # Setup cookie jar handler
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    
    # 1. GET login page
    print("GET /login...")
    req = urllib.request.Request("http://127.0.0.1:5000/login")
    with opener.open(req) as r:
        html = r.read().decode('utf-8')
        status = r.status
    print(f"Status: {status}")
    
    # Extract CSRF token
    csrf_token = None
    for line in html.splitlines():
        if 'csrf_token' in line:
            match = re.search(r'value="([^"]+)"', line)
            if match:
                csrf_token = match.group(1)
                break
    print(f"CSRF Token: {csrf_token}")
    
    # 2. POST login
    print("POST /login...")
    data = {
        "email": "test_backup@example.com",
        "password": "password"
    }
    if csrf_token:
        data["csrf_token"] = csrf_token
        
    encoded_data = urllib.parse.urlencode(data).encode('utf-8')
    req = urllib.request.Request("http://127.0.0.1:5000/login", data=encoded_data, method="POST")
    try:
        with opener.open(req) as r:
            status = r.status
            print(f"Status: {status}")
            print(f"URL: {r.url}")
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code}")
        print(e.read().decode('utf-8')[:1000])
        return

    # 3. GET /admin/dashboard
    print("GET /admin/dashboard...")
    req = urllib.request.Request("http://127.0.0.1:5000/admin/dashboard")
    try:
        with opener.open(req) as r:
            status = r.status
            print(f"Status: {status}")
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code}")
        print(e.read().decode('utf-8')[:2000])

if __name__ == "__main__":
    test_request()
