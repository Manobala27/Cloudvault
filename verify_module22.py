import os
from app import create_app, db, bcrypt
from app.models import User, APIKey, File
from app.services.api_key_service import api_key_service
from datetime import datetime, timezone
import json
import hashlib

def verify_module22():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        print("--- MODULE 22 VERIFICATION ---")
        
        # 1. Check User
        user = User.query.filter_by(email='test_api@example.com').first()
        if not user:
            hashed_password = bcrypt.generate_password_hash('password').decode('utf-8')
            user = User(username='test_api', email='test_api@example.com', password=hashed_password)
            db.session.add(user)
            db.session.commit()
            
        # Clean old keys for this test user
        APIKey.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        
        # 2. Test API Key Service directly
        print("1. Testing API Key Service...")
        raw_key, api_key = api_key_service.generate_api_key(user.id, "Test Key")
        if raw_key and api_key and raw_key.startswith('cv_'):
            print("   [OK] API Key generated correctly with prefix 'cv_'.")
        else:
            print(f"   [FAIL] Invalid generated key: {raw_key}")
            
        # 3. Test verification logic
        verified_user = api_key_service.verify_api_key(raw_key)
        if verified_user and verified_user.id == user.id:
            print("   [OK] API Key verified successfully using SHA256.")
        else:
            print("   [FAIL] API Key verification failed.")
            
        # 4. Test REST Endpoints via Test Client
        print("2. Testing REST Endpoints...")
        with app.test_client() as client:
            # Test Without Header
            res = client.get('/api/v1/files')
            if res.status_code == 401:
                print("   [OK] GET /api/v1/files WITHOUT auth returns 401 Unauthorized.")
            else:
                print(f"   [FAIL] Expected 401, got {res.status_code}")
                
            # Test With Invalid Header
            res = client.get('/api/v1/files', headers={'Authorization': 'Bearer cv_fake123'})
            if res.status_code == 401:
                print("   [OK] GET /api/v1/files WITH INVALID auth returns 401 Unauthorized.")
            else:
                print(f"   [FAIL] Expected 401, got {res.status_code}")
                
            # Test With Valid Header
            res = client.get('/api/v1/files', headers={'Authorization': f'Bearer {raw_key}'})
            if res.status_code == 200:
                data = res.get_json()
                if data.get('success'):
                    print("   [OK] GET /api/v1/files WITH VALID auth returns 200 OK and valid JSON.")
                else:
                    print("   [FAIL] Response was 200 but JSON success was false.")
            else:
                print(f"   [FAIL] Expected 200, got {res.status_code}")
                
        # 5. Test Revocation
        print("3. Testing Key Revocation...")
        api_key_service.revoke_key(api_key.id, user.id)
        if not api_key.is_active:
            print("   [OK] API Key successfully revoked.")
        else:
            print("   [FAIL] API Key revocation failed.")
            
        verified_revoked = api_key_service.verify_api_key(raw_key)
        if verified_revoked is None:
            print("   [OK] Revoked API key cannot be verified.")
        else:
            print("   [FAIL] Revoked API key still verified successfully!")
            
        print("--- MODULE 22 VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    verify_module22()
