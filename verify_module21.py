import os
import sys

# Set up the path to the app directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models import User
from app.services.two_factor_service import two_factor_service
import pyotp

def verify_module21():
    print("--- MODULE 21 VERIFICATION ---")
    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        user = User.query.first()
        if not user:
            from app import bcrypt
            hashed_password = bcrypt.generate_password_hash('password').decode('utf-8')
            user = User(username='test_2fa', email='test_2fa@example.com', password=hashed_password)
            db.session.add(user)
            db.session.commit()
            print("Created test user.")
        
        # Reset 2FA state for test
        user.two_factor_enabled = False
        user.two_factor_secret = None
        user.backup_codes = None
        user.trusted_device_until = None
        db.session.commit()

        print("1. Testing 2FA Service...")
        secret = two_factor_service.generate_secret()
        if secret and len(secret) == 32:
             print("   [OK] Secret generated successfully.")
        else:
             print("   [FAIL] Secret generation failed.")
             
        uri = two_factor_service.get_totp_uri(user.email, secret)
        if uri.startswith("otpauth://totp/CloudVault"):
             print("   [OK] TOTP URI generated successfully.")
        else:
             print("   [FAIL] TOTP URI generation failed.")
             
        qr_code = two_factor_service.generate_qr_code(uri)
        if qr_code:
             print("   [OK] QR Code generated successfully.")
        else:
             print("   [FAIL] QR Code generation failed.")
             
        totp = pyotp.TOTP(secret)
        valid_token = totp.now()
        
        if two_factor_service.verify_totp(secret, valid_token):
             print("   [OK] TOTP verification succeeded.")
        else:
             print("   [FAIL] TOTP verification failed.")
             
        raw_codes = two_factor_service.generate_recovery_codes(user)
        if len(raw_codes) == 10 and user.backup_codes:
             print("   [OK] Recovery codes generated and hashed successfully.")
        else:
             print("   [FAIL] Recovery code generation failed.")
             
        if two_factor_service.verify_recovery_code(user, raw_codes[0]):
             print("   [OK] Recovery code verification succeeded.")
             # Make sure it was consumed
             import json
             codes_left = len(json.loads(user.backup_codes))
             if codes_left == 9:
                 print("   [OK] Recovery code was properly consumed.")
             else:
                 print(f"   [FAIL] Recovery code not consumed properly. Remaining: {codes_left}")
        else:
             print("   [FAIL] Recovery code verification failed.")

        print("2. Testing Security Routes...")
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['_user_id'] = str(user.id)
                sess['_fresh'] = True
            
            # GET Settings
            res = client.get('/security/')
            if res.status_code == 200:
                print("   [OK] GET /security/ successfully loaded.")
            else:
                print(f"   [FAIL] GET /security/ returned {res.status_code}")
                
            # Simulate setup
            with client.session_transaction() as sess:
                sess['temp_2fa_secret'] = secret
                
            # POST Enable 2FA
            res = client.post('/security/2fa/enable', json={'token': valid_token})
            if res.status_code == 200 and res.json.get('success'):
                print("   [OK] POST /security/2fa/enable succeeded.")
            else:
                print(f"   [FAIL] POST /security/2fa/enable failed: {res.get_json()}")
                
        # Validate 2FA intercept on Login
        with app.test_client() as new_client:
            # Explicitly clear session just in case
            with new_client.session_transaction() as sess:
                sess.clear()
                
            # Disable CSRF for testing
            new_client.application.config['WTF_CSRF_ENABLED'] = False
                
            res = new_client.post('/login', data={'email': user.email, 'password': 'password', 'csrf_token': 'dummy'})
            if res.status_code == 302 and '/security/2fa/verify' in res.headers.get('Location', ''):
                print("   [OK] Login properly redirects to 2FA verification.")
            else:
                print(f"   [FAIL] Login did not intercept 2FA. Status: {res.status_code}, Location: {res.headers.get('Location', '')}")

        print("--- MODULE 21 VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    verify_module21()
