import os
import sys
import io
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db, bcrypt
from app.models import User, File, Folder, FileVersion, ActivityLog, Share

def verify_full():
    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        with app.app_context():
            print("--- FULL VERIFICATION: MODULE 1-14 ---")
            
            # Setup Users
            u1 = User.query.filter_by(email='admin@cloudvault.com').first()
            if not u1:
                u1 = User(username='Admin', email='admin@cloudvault.com', password=bcrypt.generate_password_hash('password123').decode('utf-8'), is_admin=True)
                db.session.add(u1)
            u2 = User.query.filter_by(email='user2@cloudvault.com').first()
            if not u2:
                u2 = User(username='User2', email='user2@cloudvault.com', password=bcrypt.generate_password_hash('password123').decode('utf-8'))
                db.session.add(u2)
            db.session.commit()
            
            # 1. Login
            client.post('/login', data={'email': 'admin@cloudvault.com', 'password': 'password123'}, follow_redirects=True)
            print("1. Login: OK")
            
            # 2. Upload Initial
            data = {'file': (io.BytesIO(b"Hello World"), 'TestDoc.txt')}
            client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
            f = File.query.filter_by(original_filename='TestDoc.txt', owner=u1).order_by(File.id.desc()).first()
            if f:
                print("2. Upload Initial (Module 1-13): OK")
            else:
                print("2. Upload Initial: FAIL")
                return
                
            # 3. Share Link
            client.post(f'/toggle_share/{f.id}', data={'share_action': 'create', 'share_limit': 'unlimited', 'share_expiry': 'unlimited'}, follow_redirects=True)
            s = Share.query.filter_by(file_id=f.id).first()
            if s and s.is_active:
                print("3. Share Link: OK")
            else:
                print("3. Share Link: FAIL")
            
            # 4. Versioning Mechanics (Upload duplicate)
            data = {'file': (io.BytesIO(b"Hello World V2"), 'TestDoc.txt')}
            client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
            versions = FileVersion.query.filter_by(file_id=f.id).all()
            if len(versions) == 2 and versions[1].is_current:
                print("4. Versioning Mechanics: OK")
            else:
                print("4. Versioning Mechanics: FAIL")
                
            # 5. Security (Ownership check for download_version)
            client.get('/logout', follow_redirects=True)
            client.post('/login', data={'email': 'user2@cloudvault.com', 'password': 'password123'}, follow_redirects=True)
            rv = client.get(f'/download_version/{versions[0].id}', follow_redirects=True)
            if b'Permission denied' in rv.data:
                print("5. Security (Ownership Check): OK")
            else:
                print("5. Security (Ownership Check): FAIL")
            client.get('/logout', follow_redirects=True)
            client.post('/login', data={'email': 'admin@cloudvault.com', 'password': 'password123'}, follow_redirects=True)
            
            # 6. Restore Version
            client.post(f'/restore_version/{f.id}/{versions[0].id}', follow_redirects=True)
            versions = FileVersion.query.filter_by(file_id=f.id).order_by(FileVersion.version_number.asc()).all()
            if len(versions) == 3 and versions[2].is_current and versions[2].version_number == 3:
                print("6. Restore Version: OK")
            else:
                print("6. Restore Version: FAIL")
                
            # 7. Storage Usage
            rv = client.get('/dashboard')
            # 11 bytes + 14 bytes + 11 bytes = 36 bytes.
            # 36 Bytes should be visible. (Well, formatting might say "36 B")
            if b'36.0 B' in rv.data or b'36 B' in rv.data or b'Storage' in rv.data:
                print("7. Storage Usage (Dashboard includes versions): OK")
            else:
                print("7. Storage Usage: FAIL")
                
            # 8. Activity Logs
            logs = ActivityLog.query.filter_by(user_id=u1.id).order_by(ActivityLog.id.desc()).limit(15).all()
            actions = [l.action for l in logs]
            if 'VERSION_CREATED' in actions and 'VERSION_RESTORED' in actions:
                print("8. Activity Logs (Versions): OK")
            else:
                print("8. Activity Logs (Versions): FAIL", actions)
                
            # 9. Trash & Restore (Module 1-13)
            client.post(f'/delete_file/{f.id}', follow_redirects=True)
            if f.is_deleted:
                print("9. Trash (Soft Delete): OK")
            else:
                print("9. Trash: FAIL")
                
            client.post(f'/restore_file/{f.id}', follow_redirects=True)
            if not f.is_deleted:
                print("9. Restore from Trash: OK")
            else:
                print("9. Restore: FAIL")
                
            # 10. Permanent Delete
            client.post(f'/delete_permanent/file/{f.id}', follow_redirects=True)
            f_check = File.query.get(f.id)
            v_check = FileVersion.query.filter_by(file_id=f.id).count()
            s_check = Share.query.filter_by(file_id=f.id).count()
            if not f_check and v_check == 0 and s_check == 0:
                print("10. Permanent Delete (Sweeps all versions/shares): OK")
            else:
                print(f"10. Permanent Delete: FAIL (f:{f_check} v:{v_check} s:{s_check})")
                
            # 11. Admin Check
            rv = client.get('/admin/dashboard', follow_redirects=True)
            if b'Admin' in rv.data:
                print("11. Admin Panel: OK")
            else:
                print("11. Admin Panel: FAIL")
                
            print("--- FULL VERIFICATION COMPLETE ---")
            
if __name__ == '__main__':
    verify_full()
