import os
import sys
import io

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db, bcrypt
from app.models import User, File, FileVersion, ActivityLog

def verify_all():
    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        with app.app_context():
            print("--- Starting Verification for Module 14 ---")
            
            # Fetch Admin User
            admin_user = User.query.get(1)
            
            # Reset Admin Password for testing
            admin_pw_hash = bcrypt.generate_password_hash('password123').decode('utf-8')
            admin_user.password = admin_pw_hash
            db.session.commit()
            
            # Test Login as Admin
            print("Testing Login...")
            rv = client.post('/login', data={'email': admin_user.email, 'password': 'password123'}, follow_redirects=True)
            if b'Dashboard' not in rv.data and b'Login successful' not in rv.data:
                print("FAIL: Failed to login.")
                return

            print("PASS: Logged in.")

            # Test Upload 1
            print("Testing Upload Version 1...")
            data = {'file': (io.BytesIO(b"Version 1 Content"), 'VersioningTest.txt')}
            rv = client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
            
            # Test Upload 2
            print("Testing Upload Version 2...")
            data = {'file': (io.BytesIO(b"Version 2 Content"), 'VersioningTest.txt')}
            rv = client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)

            # Test Upload 3
            print("Testing Upload Version 3...")
            data = {'file': (io.BytesIO(b"Version 3 Content"), 'VersioningTest.txt')}
            rv = client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)

            # Check DB for File and Versions
            f = File.query.filter_by(original_filename='VersioningTest.txt').order_by(File.id.desc()).first()
            if not f:
                print("FAIL: File not found in DB.")
                return
                
            versions = FileVersion.query.filter_by(file_id=f.id).order_by(FileVersion.version_number.asc()).all()
            if len(versions) == 3:
                print("PASS: 3 versions created successfully.")
            else:
                print(f"FAIL: Expected 3 versions, got {len(versions)}.")
                
            if versions[2].is_current and not versions[0].is_current and not versions[1].is_current:
                print("PASS: V3 is current, others are not.")
            else:
                print("FAIL: is_current flag is wrong.")
                
            # Test Download Version 1
            print("Testing Download Version 1...")
            v1_id = versions[0].id
            rv = client.get(f'/download_version/{v1_id}')
            if rv.status_code in [302, 301]:
                print("PASS: Download Version endpoint redirected successfully.")
            else:
                print(f"FAIL: Download endpoint returned {rv.status_code}")
                
            # Test Restore Version 1
            print("Testing Restore Version 1...")
            rv = client.post(f'/restore_version/{f.id}/{v1_id}', follow_redirects=True)
            
            db.session.refresh(f)
            restored_versions = FileVersion.query.filter_by(file_id=f.id).order_by(FileVersion.version_number.asc()).all()
            
            if len(restored_versions) == 4:
                print("PASS: V4 created upon restore.")
            else:
                print(f"FAIL: Expected 4 versions after restore, got {len(restored_versions)}.")
                
            if restored_versions[-1].is_current and not restored_versions[-2].is_current:
                print("PASS: V4 is current.")
            else:
                print("FAIL: is_current flag is wrong after restore.")
                
            # Verify Activity Logs
            print("Verifying Activity Logs...")
            logs = ActivityLog.query.order_by(ActivityLog.id.desc()).limit(10).all()
            actions = [log.action for log in logs]
            if 'VERSION_CREATED' in actions and 'VERSION_RESTORED' in actions and 'VERSION_DOWNLOADED' in actions:
                print("PASS: Activity Logs recorded correctly.")
            else:
                print(f"FAIL: Missing expected Activity Logs. Actions found: {actions}")
                
            # Test Permanent Delete
            print("Testing Permanent Delete...")
            # We must first move it to trash to access it in trash, but delete_permanent_file doesn't check if it's in trash.
            rv = client.post(f'/delete_permanent/file/{f.id}', follow_redirects=True)
            
            f_check = File.query.get(f.id)
            v_check = FileVersion.query.filter_by(file_id=f.id).count()
            
            if not f_check and v_check == 0:
                print("PASS: File and all versions deleted from database.")
            else:
                print("FAIL: File or versions still exist in database.")
                
            print("--- Verification Complete ---")

if __name__ == '__main__':
    verify_all()
