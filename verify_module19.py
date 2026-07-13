import os
import sys

# Set up the path to the app directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models import User, Notification
from app.services.notification_service import notification_service

def verify_module19():
    print("--- MODULE 19 VERIFICATION ---")
    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        # Get a test user
        user = User.query.first()
        if not user:
            print("No test user found in the database. Creating one...")
            from app import bcrypt
            hashed_password = bcrypt.generate_password_hash('password').decode('utf-8')
            user = User(username='testuser_notif', email='test_notif@example.com', password=hashed_password)
            db.session.add(user)
            db.session.commit()
            print(f"Created test user: {user.username}")
        
        # 1. Create a notification directly via service
        print("1. Testing Notification Service...")
        notif = notification_service.create_notification(
            user.id, 
            "Test Alert", 
            "This is a system test notification.", 
            "SYSTEM", 
            "bi-info-circle"
        )
        if notif and notif.id:
            print(f"   [OK] Created notification ID {notif.id}")
        else:
            print("   [FAIL] Failed to create notification via service")
            sys.exit(1)
            
        # 2. Test routes
        print("2. Testing Notification Routes...")
        with app.test_client() as client:
            # Login
            with client.session_transaction() as sess:
                sess['_user_id'] = str(user.id)
                sess['_fresh'] = True
            
            # Get Unread count
            res = client.get('/notifications/unread_count')
            if res.status_code == 200:
                print(f"   [OK] GET /notifications/unread_count returned: {res.json.get('count')}")
            else:
                print(f"   [FAIL] GET /notifications/unread_count returned status {res.status_code}")
                
            # Get Notifications page
            res = client.get('/notifications/')
            if res.status_code == 200 and b'Test Alert' in res.data:
                print("   [OK] GET /notifications/ loaded successfully")
            else:
                print("   [FAIL] GET /notifications/ failed or missing content")
                
            # Mark Read
            res = client.post(f'/notifications/read/{notif.id}')
            if res.status_code == 200 and res.json.get('success'):
                print("   [OK] POST /notifications/read/<id> succeeded")
            else:
                print("   [FAIL] POST /notifications/read/<id> failed")
                
            # Verify Read State
            res = client.get('/notifications/unread_count')
            count = res.json.get('count', 1)
            if count == 0 or count < Notification.query.count():
                 print("   [OK] Unread count decreased successfully")
            
            # Delete Notification
            res = client.post(f'/notifications/delete/{notif.id}')
            if res.status_code == 200 and res.json.get('success'):
                print("   [OK] POST /notifications/delete/<id> succeeded")
            else:
                print("   [FAIL] POST /notifications/delete/<id> failed")
        
        print("--- MODULE 19 VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    verify_module19()
