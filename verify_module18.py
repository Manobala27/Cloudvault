import os
import sys
import json
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, File, Folder, Tag, ActivityLog, Share

def verify_module18():
    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        with app.app_context():
            print("--- MODULE 18 VERIFICATION ---")
            
            # Setup User
            u1 = User.query.filter_by(email='admin@cloudvault.com').first()
            if not u1:
                print("FAIL: Admin user not found.")
                return

            client.post('/login', data={'email': 'admin@cloudvault.com', 'password': 'password123'}, follow_redirects=True)
            
            # Use an existing file to test the preview route
            test_file = File.query.filter_by(owner=u1, is_deleted=False).first()
            if not test_file:
                print("FAIL: No files available for testing preview.")
                return

            print("Testing preview with file:", test_file.original_filename)

            # 1. Access Preview Route
            res = client.get(f'/preview/{test_file.id}')
            if res.status_code == 200 and b'id="preview-canvas"' in res.data:
                print("1. UI GET /preview/<id>: OK")
            else:
                print(f"1. UI GET /preview/<id>: FAIL ({res.status_code})")

            # 2. Activity Log generated
            log = ActivityLog.query.filter_by(user_id=u1.id, action='PREVIEW_OPENED', file_name=test_file.original_filename).order_by(ActivityLog.id.desc()).first()
            if log:
                print("2. Activity Logging (PREVIEW_OPENED): OK")
            else:
                print("2. Activity Logging (PREVIEW_OPENED): FAIL")
                
            # 3. Access Shared Link Preview
            share_record = Share.query.filter_by(file_id=test_file.id, is_active=True).first()
            
            # Create a share if none exists
            if not share_record:
                import uuid
                from datetime import timedelta
                share_record = Share(
                    file_id=test_file.id,
                    share_token=str(uuid.uuid4()),
                    is_active=True
                )
                db.session.add(share_record)
                db.session.commit()
            
            # Logout to simulate external user
            client.get('/logout', follow_redirects=True)
            
            res = client.get(f'/shared/{share_record.share_token}/preview')
            if res.status_code == 200 and b'id="preview-canvas"' in res.data and b'is_shared=True' not in res.data:
                # Note: `is_shared` is passed to context so we might not see it literally unless injected.
                # Just checking 200 and canvas is enough.
                print("3. UI GET /shared/<token>/preview: OK")
            else:
                print(f"3. UI GET /shared/<token>/preview: FAIL ({res.status_code})")
                
            print("--- MODULE 18 VERIFICATION COMPLETE ---")

if __name__ == '__main__':
    verify_module18()
