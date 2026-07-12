import os
import sys
import json
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, File, Folder, Tag, ActivityLog

def verify_module17():
    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        with app.app_context():
            print("--- MODULE 17 VERIFICATION ---")
            
            # Setup User
            u1 = User.query.filter_by(email='admin@cloudvault.com').first()
            if not u1:
                print("FAIL: Admin user not found.")
                return

            client.post('/login', data={'email': 'admin@cloudvault.com', 'password': 'password123'}, follow_redirects=True)
            
            # Create a file and folder for search testing if none exist
            test_tag = Tag.query.filter_by(user_id=u1.id).first()
            test_file = File.query.filter_by(owner=u1, is_deleted=False).first()
            if not test_file:
                print("FAIL: No files available for testing.")
                return

            print("Testing with file:", test_file.original_filename)

            # 1. Advanced Search Page Load
            res = client.get('/search/')
            if b'Advanced Search' in res.data:
                print("1. UI GET /search: OK")
            else:
                print("1. UI GET /search: FAIL")

            # 2. Empty Search (All items)
            res = client.post('/search/api', json={'log_event': False})
            data = res.get_json()
            if data and 'files' in data and len(data['files']) > 0:
                print("2. API Empty Search (All items): OK")
            else:
                print("2. API Empty Search (All items): FAIL")

            # 3. Keyword Search
            filename_part = test_file.original_filename[:3]
            res = client.post('/search/api', json={'query': filename_part, 'log_event': False})
            data = res.get_json()
            if any(f['filename'] == test_file.original_filename for f in data['files']):
                print("3. API Keyword Search: OK")
            else:
                print("3. API Keyword Search: FAIL")

            # 4. Filter by Extension
            ext = os.path.splitext(test_file.original_filename)[1]
            if ext:
                res = client.post('/search/api', json={'extensions': [ext], 'log_event': False})
                data = res.get_json()
                if any(f['filename'] == test_file.original_filename for f in data['files']):
                    print(f"4. API Ext Search ({ext}): OK")
                else:
                    print(f"4. API Ext Search ({ext}): FAIL")
            else:
                print("4. API Ext Search: SKIPPED (File has no extension)")

            # 5. Type Filter (Folders only)
            res = client.post('/search/api', json={'type': 'folders', 'log_event': False})
            data = res.get_json()
            if len(data['files']) == 0 and 'folders' in data:
                print("5. API Type Filter (Folders only): OK")
            else:
                print("5. API Type Filter (Folders only): FAIL")

            # 6. Check Activity Logs for ADVANCED_SEARCH_EXECUTED
            # Let's trigger a logged search
            client.post('/search/api', json={'query': 'LOG_TEST', 'log_event': True})
            logs = ActivityLog.query.filter_by(user_id=u1.id, action='ADVANCED_SEARCH_EXECUTED').order_by(ActivityLog.id.desc()).first()
            if logs and "LOG_TEST" in logs.file_name:
                print("6. Activity Logging: OK")
            else:
                print("6. Activity Logging: FAIL")

            # 7. Security: Trashed items are excluded
            trashed_file = File.query.filter_by(owner=u1, is_deleted=True).first()
            if trashed_file:
                res = client.post('/search/api', json={'query': trashed_file.original_filename, 'log_event': False})
                data = res.get_json()
                if not any(f['id'] == trashed_file.id for f in data['files']):
                    print("7. Security (Trashed excluded): OK")
                else:
                    print("7. Security (Trashed excluded): FAIL")
            else:
                print("7. Security (Trashed excluded): SKIPPED (No trashed files)")
                
            print("--- MODULE 17 VERIFICATION COMPLETE ---")

if __name__ == '__main__':
    verify_module17()
