import os
import sys
import io

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, File, Folder, Tag, ActivityLog

def verify_module16():
    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        with app.app_context():
            print("--- MODULE 16 VERIFICATION ---")
            
            # Setup Users
            u1 = User.query.filter_by(email='admin@cloudvault.com').first()
            u2 = User.query.filter_by(email='user2@cloudvault.com').first()
            
            # Login as Admin
            client.post('/login', data={'email': 'admin@cloudvault.com', 'password': 'password123'}, follow_redirects=True)
            
            # 1. Create a Tag
            client.post('/tags/create', data={'tag_name': 'TestTag', 'tag_color': '#ff0000'}, follow_redirects=True)
            tag = Tag.query.filter_by(name='TestTag', user_id=u1.id).first()
            if tag:
                print("1. Create Tag: OK")
            else:
                print("1. Create Tag: FAIL")
                return
                
            # Setup test files
            f = File.query.filter_by(owner=u1).order_by(File.id.desc()).first()
            fld = Folder.query.filter_by(owner=u1).order_by(Folder.id.desc()).first()
            
            # 2. Assign Tag to File
            res = client.post(f'/tags/assign/file/{f.id}', json={'tag_id': tag.id, 'assign': True})
            if res.status_code == 200 and tag in f.tags:
                print("2. Assign Tag to File: OK")
            else:
                print("2. Assign Tag to File: FAIL")
                
            # 3. Assign Tag to Folder
            res = client.post(f'/tags/assign/folder/{fld.id}', json={'tag_id': tag.id, 'assign': True})
            if res.status_code == 200 and tag in fld.tags:
                print("3. Assign Tag to Folder: OK")
            else:
                print("3. Assign Tag to Folder: FAIL")
                
            # 4. View Tag Filter Page
            res = client.get(f'/tags/view/{tag.id}')
            if f.original_filename.encode() in res.data and fld.name.encode() in res.data:
                print("4. Tag View Page works: OK")
            else:
                print("4. Tag View Page works: FAIL")
                
            # 5. Activity Logs check
            logs = ActivityLog.query.filter_by(user_id=u1.id).order_by(ActivityLog.id.desc()).limit(10).all()
            actions = [l.action for l in logs]
            if 'TAG_CREATED' in actions and 'ITEM_TAGGED' in actions:
                print("5. Activity Logs: OK")
            else:
                print("5. Activity Logs: FAIL")
                
            # 6. Security (Access other user's tag)
            client.get('/logout', follow_redirects=True)
            client.post('/login', data={'email': 'user2@cloudvault.com', 'password': 'password123'}, follow_redirects=True)
            
            res = client.get(f'/tags/view/{tag.id}')
            if res.status_code == 302: # Redirects with flash message
                print("6. Security Tag Ownership validation: OK")
            else:
                print("6. Security Tag Ownership validation: FAIL", res.status_code)
                
            # 7. Delete Tag
            client.get('/logout', follow_redirects=True)
            client.post('/login', data={'email': 'admin@cloudvault.com', 'password': 'password123'}, follow_redirects=True)
            
            client.post(f'/tags/delete/{tag.id}', follow_redirects=True)
            tag_check = Tag.query.filter_by(id=tag.id).first()
            if not tag_check and tag not in f.tags:
                print("7. Delete Tag & Cascade Cleanup: OK")
            else:
                print("7. Delete Tag & Cascade Cleanup: FAIL")
                
            print("--- MODULE 16 VERIFICATION COMPLETE ---")

if __name__ == '__main__':
    verify_module16()
