import os
from app import create_app, db
from app.models import User, Backup, Tag, Folder
from app.services.backup_service import backup_service
import json

def verify_module23():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        print("--- MODULE 23 VERIFICATION ---")
        
        # 1. Setup Test User & Data
        user = User.query.filter_by(username='test_backup').first()
        if not user:
            from app import bcrypt
            hashed_password = bcrypt.generate_password_hash('password').decode('utf-8')
            user = User(username='test_backup', email='test_backup@example.com', password=hashed_password)
            db.session.add(user)
            db.session.commit()
            
        # Clean old backups
        backups = Backup.query.filter_by(user_id=user.id).all()
        for b in backups:
            backup_service.delete_backup(b.id, user.id)
            
        # Create some fake metadata
        Tag.query.filter_by(user_id=user.id, name="BackupTag").delete()
        Folder.query.filter_by(user_id=user.id, name="BackupFolder").delete()
        db.session.commit()
        
        t = Tag(name="BackupTag", color_hex="#000000", user_id=user.id)
        f = Folder(name="BackupFolder", user_id=user.id)
        db.session.add_all([t, f])
        db.session.commit()
        
        # 2. Test Backup Generation
        print("1. Testing Backup Generation...")
        success, backup_id = backup_service.generate_backup(user.id, "Test Backup", "Full")
        if success:
            print(f"   [OK] Backup successfully generated with ID: {backup_id}")
        else:
            print(f"   [FAIL] Backup generation failed: {backup_id}")
            return
            
        # 3. Test File Validation
        print("2. Testing Backup File Validity...")
        b = Backup.query.get(backup_id)
        if b and os.path.exists(b.storage_path):
            with open(b.storage_path, 'r', encoding='utf-8') as f_json:
                data = json.load(f_json)
                if data['metadata']['backup_version'] == '1.0' and data['metadata']['user_id'] == user.id:
                    print("   [OK] JSON file structure matches schema.")
                    if any(t['name'] == 'BackupTag' for t in data.get('tags', [])):
                        print("   [OK] Tags correctly exported.")
                    else:
                        print("   [FAIL] Tag not found in backup file.")
                else:
                    print("   [FAIL] Invalid JSON metadata structure.")
        else:
            print("   [FAIL] Backup file not found on disk.")
            
        # 4. Test Backup Restoration
        print("3. Testing Backup Restoration...")
        # delete tag to simulate restore
        Tag.query.filter_by(user_id=user.id, name="BackupTag").delete()
        db.session.commit()
        
        success, msg = backup_service.restore_backup(backup_id, user.id, ['tags'])
        if success:
            restored_tag = Tag.query.filter_by(user_id=user.id, name="BackupTag").first()
            if restored_tag:
                print("   [OK] Backup safely restored missing data (Tags).")
            else:
                print("   [FAIL] Restore process did not recreate the tag.")
        else:
            print(f"   [FAIL] Restore failed: {msg}")
            
        # 5. Clean up
        print("4. Testing Backup Deletion...")
        success = backup_service.delete_backup(backup_id, user.id)
        if success and not os.path.exists(b.storage_path):
            print("   [OK] Backup successfully deleted from DB and Disk.")
        else:
            print("   [FAIL] Backup deletion failed or file still exists on disk.")
            
        print("--- MODULE 23 VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    verify_module23()
