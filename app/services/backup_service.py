import json
import os
import uuid
from datetime import datetime, timezone
from app import db
from app.models import Backup, File, Folder, FileVersion, Tag, Share, ActivityLog, User
from flask import current_app

class BackupService:
    @staticmethod
    def _get_backup_dir():
        backup_dir = os.path.join(current_app.root_path, '..', 'instance', 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        return backup_dir

    @staticmethod
    def generate_backup(user_id, backup_name, backup_type='Full'):
        user = User.query.get(user_id)
        if not user:
            return False, "User not found."

        data = {
            'metadata': {
                'backup_version': '1.0',
                'backup_date': datetime.now(timezone.utc).isoformat(),
                'CloudVault_version': '23.0',
                'user_id': user.id,
                'username': user.username,
                'backup_type': backup_type
            },
            'folders': [],
            'files': [],
            'tags': [],
            'favorites': [],
            'shares': [],
            'settings': {}
        }

        if backup_type in ['Full', 'Metadata']:
            # Folders
            folders = Folder.query.filter_by(user_id=user.id, is_deleted=False).all()
            for f in folders:
                data['folders'].append({
                    'id': f.id,
                    'name': f.name,
                    'parent_id': f.parent_id,
                    'is_favorite': f.is_favorite
                })

            # Tags
            tags = Tag.query.filter_by(user_id=user.id).all()
            for t in tags:
                data['tags'].append({
                    'id': t.id,
                    'name': t.name,
                    'color_hex': t.color_hex
                })

            # Files
            files = File.query.filter_by(user_id=user.id, is_deleted=False).all()
            for f in files:
                file_data = {
                    'id': f.id,
                    'original_filename': f.original_filename,
                    's3_key': f.filename,
                    'file_size': f.file_size,
                    'folder_id': f.folder_id,
                    'is_favorite': f.is_favorite,
                    'versions': [],
                    'tags': [t.id for t in f.tags]
                }
                
                for v in f.versions:
                    file_data['versions'].append({
                        'version_number': v.version_number,
                        's3_key': v.s3_key,
                        'file_size': v.file_size,
                        'is_current': v.is_current
                    })
                data['files'].append(file_data)

            # Shares
            # Since Share is tied to File, and File is tied to User, we can get shares via user's files
            for f in files:
                for s in f.shares:
                    data['shares'].append({
                        'file_id': s.file_id,
                        'share_token': s.share_token,
                        'expires_at': s.expires_at.isoformat() if s.expires_at else None,
                        'download_limit': s.download_limit,
                        'download_count': s.download_count,
                        'is_active': s.is_active
                    })

        if backup_type in ['Full', 'Settings']:
            data['settings'] = {
                'two_factor_enabled': user.two_factor_enabled,
                'theme': 'auto' # placeholder for any future settings
            }

        # Save to disk
        backup_filename = f"backup_{user_id}_{uuid.uuid4().hex}.json"
        storage_path = os.path.join(BackupService._get_backup_dir(), backup_filename)
        
        with open(storage_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
        backup_size = os.path.getsize(storage_path)

        # Create DB record
        backup = Backup(
            user_id=user_id,
            backup_name=backup_name,
            backup_type=backup_type,
            backup_size=backup_size,
            storage_path=storage_path,
            status='completed'
        )
        db.session.add(backup)
        
        # Log
        log = ActivityLog(user_id=user_id, action='BACKUP_CREATED', file_name=f"Created {backup_type} backup: {backup_name}")
        db.session.add(log)
        db.session.commit()

        return True, backup.id

    @staticmethod
    def get_backup_path(backup_id, user_id):
        backup = Backup.query.filter_by(id=backup_id, user_id=user_id).first()
        if backup and os.path.exists(backup.storage_path):
            return backup.storage_path
        return None

    @staticmethod
    def delete_backup(backup_id, user_id):
        backup = Backup.query.filter_by(id=backup_id, user_id=user_id).first()
        if backup:
            if os.path.exists(backup.storage_path):
                os.remove(backup.storage_path)
            db.session.delete(backup)
            
            log = ActivityLog(user_id=user_id, action='BACKUP_DELETED', file_name=f"Deleted backup: {backup.backup_name}")
            db.session.add(log)
            db.session.commit()
            return True
        return False
        
    @staticmethod
    def restore_backup(backup_id, user_id, restore_options):
        """
        Restores parts of the backup without deleting existing items unless necessary.
        restore_options is a list of strings: ['folders', 'favorites', 'tags', 'shares', 'settings']
        """
        backup = Backup.query.filter_by(id=backup_id, user_id=user_id).first()
        if not backup or not os.path.exists(backup.storage_path):
            return False, "Backup not found."

        try:
            with open(backup.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return False, f"Failed to read backup: {e}"

        # Simplistic restore for tags and favorites
        if 'tags' in restore_options and 'tags' in data:
            for t_data in data['tags']:
                existing_tag = Tag.query.filter_by(user_id=user_id, name=t_data['name']).first()
                if not existing_tag:
                    new_tag = Tag(name=t_data['name'], color_hex=t_data['color_hex'], user_id=user_id)
                    db.session.add(new_tag)
        
        if 'favorites' in restore_options and 'files' in data:
            # We map files by s3_key since IDs might have changed if this was a fresh system
            for f_data in data['files']:
                if f_data.get('is_favorite'):
                    f = File.query.filter_by(user_id=user_id, filename=f_data['s3_key']).first()
                    if f:
                        f.is_favorite = True
                        
            for fld_data in data.get('folders', []):
                if fld_data.get('is_favorite'):
                    fld = Folder.query.filter_by(user_id=user_id, name=fld_data['name']).first()
                    if fld:
                        fld.is_favorite = True

        log = ActivityLog(user_id=user_id, action='BACKUP_RESTORED', file_name=f"Restored from backup: {backup.backup_name}")
        db.session.add(log)
        db.session.commit()

        return True, "Backup restored successfully."

backup_service = BackupService()
