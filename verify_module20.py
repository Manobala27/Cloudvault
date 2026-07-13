import os
import sys

# Set up the path to the app directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models import User
from app.services.analytics_service import analytics_service

def verify_module20():
    print("--- MODULE 20 VERIFICATION ---")
    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        user = User.query.first()
        if not user:
            from app import bcrypt
            hashed_password = bcrypt.generate_password_hash('password').decode('utf-8')
            user = User(username='test_analytics', email='test_analytics@example.com', password=hashed_password)
            db.session.add(user)
            db.session.commit()
            print("Created test user.")
        
        print("1. Testing Analytics Service (User)...")
        try:
            data = analytics_service.get_user_analytics(user.id, 30)
            if 'storage_used' in data and 'type_counts' in data:
                print("   [OK] get_user_analytics returned valid schema.")
            else:
                print("   [FAIL] get_user_analytics schema mismatch.")
        except Exception as e:
            print(f"   [FAIL] get_user_analytics raised exception: {e}")

        print("2. Testing Analytics Service (Admin)...")
        try:
            admin_data = analytics_service.get_admin_analytics()
            if 'total_users' in admin_data and 'total_storage' in admin_data:
                print("   [OK] get_admin_analytics returned valid schema.")
            else:
                print("   [FAIL] get_admin_analytics schema mismatch.")
        except Exception as e:
            print(f"   [FAIL] get_admin_analytics raised exception: {e}")

        print("3. Testing Analytics Routes...")
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['_user_id'] = str(user.id)
                sess['_fresh'] = True
            
            res = client.get('/analytics/')
            if res.status_code == 200:
                print("   [OK] GET /analytics/ successfully loaded UI.")
            else:
                print(f"   [FAIL] GET /analytics/ returned {res.status_code}")

            res = client.get('/analytics/data?days=7')
            if res.status_code == 200 and res.is_json:
                print("   [OK] GET /analytics/data JSON endpoint works.")
            else:
                print(f"   [FAIL] GET /analytics/data returned {res.status_code}")

            res = client.get('/analytics/export/csv')
            if res.status_code == 200 and 'text/csv' in res.headers.get('Content-Type', ''):
                print("   [OK] GET /analytics/export/csv successfully exported CSV.")
            else:
                print(f"   [FAIL] GET /analytics/export/csv failed.")
                
        print("--- MODULE 20 VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    verify_module20()
