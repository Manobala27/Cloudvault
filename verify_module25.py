import os
from app import create_app

def verify_module25():
    print("--- MODULE 25 VERIFICATION ---")
    
    expected_files = [
        'Dockerfile',
        'docker-compose.yml',
        'nginx.conf',
        'gunicorn.conf.py',
        '.env.example',
        'DEPLOYMENT.md',
        'README.md',
        '.github/workflows/cloudvault.yml'
    ]
    
    root_path = os.path.dirname(os.path.abspath(__file__))
    
    print("1. Checking Infrastructure Files...")
    all_files_exist = True
    for f in expected_files:
        path = os.path.join(root_path, f)
        if os.path.exists(path):
            print(f"   [OK] Found {f}")
        else:
            print(f"   [FAIL] Missing {f}")
            all_files_exist = False
            
    if not all_files_exist:
        return
        
    print("2. Checking Flask /health Endpoint...")
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()
    
    res = client.get('/health')
    if res.status_code in [200, 503]:
        data = res.get_json()
        if 'status' in data and 'database' in data and 'aws_s3' in data:
            print(f"   [OK] /health endpoint active. Status: {data['status']}")
        else:
            print("   [FAIL] /health endpoint returned invalid JSON schema.")
    else:
        print(f"   [FAIL] /health endpoint returned status code: {res.status_code}")
        
    print("3. Checking Dockerfile Properties...")
    with open(os.path.join(root_path, 'Dockerfile'), 'r') as df:
        content = df.read()
        if 'FROM python' in content and 'gunicorn' in content and 'USER cloudvault' in content:
            print("   [OK] Dockerfile contains correct stages, non-root user, and gunicorn.")
        else:
            print("   [FAIL] Dockerfile is missing critical production directives.")
            
    print("--- MODULE 25 VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    verify_module25()
