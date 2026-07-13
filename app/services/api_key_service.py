import secrets
import string
import hashlib
from datetime import datetime, timezone
from app import db
from app.models import APIKey, User

class APIKeyService:
    @staticmethod
    def generate_api_key(user_id, name, expires_at=None):
        # Generate a secure 64-character hex key with cv_ prefix
        raw_key = 'cv_' + secrets.token_hex(32)
        
        # Hash the key with SHA256 for storage (API keys have high entropy, so fast hashes are safe)
        hashed_key = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        
        # Save to database
        api_key = APIKey(
            user_id=user_id,
            name=name,
            api_key_hash=hashed_key,
            expires_at=expires_at,
            is_active=True
        )
        db.session.add(api_key)
        db.session.commit()
        
        return raw_key, api_key
        
    @staticmethod
    def verify_api_key(raw_key):
        if not raw_key or not raw_key.startswith('cv_'):
            return None
            
        hashed_key = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        api_key = APIKey.query.filter_by(api_key_hash=hashed_key, is_active=True).first()
        
        if api_key:
            # Check expiry
            if api_key.expires_at and api_key.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
                return None
            
            return api_key.user
            
        return None
        
    @staticmethod
    def revoke_key(key_id, user_id):
        key = APIKey.query.filter_by(id=key_id, user_id=user_id).first()
        if key:
            key.is_active = False
            db.session.commit()
            return True
        return False
        
    @staticmethod
    def delete_key(key_id, user_id):
        key = APIKey.query.filter_by(id=key_id, user_id=user_id).first()
        if key:
            db.session.delete(key)
            db.session.commit()
            return True
        return False
        
    @staticmethod
    def update_last_used(key_id):
        key = APIKey.query.get(key_id)
        if key:
            key.last_used = datetime.now(timezone.utc)
            db.session.commit()

api_key_service = APIKeyService()
