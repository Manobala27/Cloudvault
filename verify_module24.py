import os
from app import create_app

def verify_module24():
    app = create_app()
    app.config['TESTING'] = True
    
    # Check if files exist
    static_dir = os.path.join(app.root_path, 'static')
    icons_dir = os.path.join(static_dir, 'icons')
    
    print("--- MODULE 24 VERIFICATION ---")
    
    print("1. Checking Static Files...")
    manifest_path = os.path.join(static_dir, 'manifest.json')
    sw_path = os.path.join(static_dir, 'service-worker.js')
    offline_path = os.path.join(static_dir, 'offline.html')
    icon_192 = os.path.join(icons_dir, 'icon-192x192.svg')
    icon_512 = os.path.join(icons_dir, 'icon-512x512.svg')
    
    files_exist = True
    for f in [manifest_path, sw_path, offline_path, icon_192, icon_512]:
        if os.path.exists(f):
            print(f"   [OK] Found {os.path.basename(f)}")
        else:
            print(f"   [FAIL] Missing {os.path.basename(f)}")
            files_exist = False
            
    if not files_exist:
        return
        
    print("2. Checking Flask Routes...")
    client = app.test_client()
    
    res = client.get('/manifest.json')
    if res.status_code == 200 and 'application/json' in res.content_type:
        print("   [OK] /manifest.json route served correctly.")
    else:
        print("   [FAIL] /manifest.json route failed.")
        
    res = client.get('/service-worker.js')
    if res.status_code == 200 and 'application/javascript' in res.content_type:
        print("   [OK] /service-worker.js route served correctly.")
    else:
        print("   [FAIL] /service-worker.js route failed.")
        
    res = client.get('/offline.html')
    if res.status_code == 200 and 'text/html' in res.content_type:
        print("   [OK] /offline.html route served correctly.")
    else:
        print("   [FAIL] /offline.html route failed.")
        
    print("3. Checking Base Template PWA Meta Tags...")
    base_template_path = os.path.join(app.root_path, 'templates', 'base.html')
    with open(base_template_path, 'r', encoding='utf-8') as f:
        content = f.read()
        if 'rel="manifest"' in content and 'manifest.json' in content:
            print("   [OK] Base template includes manifest.")
        else:
            print("   [FAIL] Base template missing manifest link.")
            
        if 'serviceWorker' in content and 'register' in content:
            print("   [OK] Base template includes Service Worker registration logic.")
        else:
            print("   [FAIL] Base template missing Service Worker logic.")
            
        if 'offline-banner' in content:
            print("   [OK] Base template includes Offline banner.")
        else:
            print("   [FAIL] Base template missing Offline banner.")
            
        if 'installAppBtn' in content:
            print("   [OK] Base template includes Install button logic.")
        else:
            print("   [FAIL] Base template missing Install button.")
            
    print("--- MODULE 24 VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    verify_module24()
