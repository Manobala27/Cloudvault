import os
from app import create_app, db
from app.models import File, Share
from datetime import datetime, timezone

app = create_app()

def migrate():
    with app.app_context():
        # Create all tables (will create the new share table)
        db.create_all()
        
        print("Starting Module 12 Migration...")
        
        # Find all files with legacy share tokens
        legacy_shares = File.query.filter(File.share_token.isnot(None)).all()
        count = 0
        
        for f in legacy_shares:
            # Check if a Share record already exists for this token
            existing_share = Share.query.filter_by(share_token=f.share_token).first()
            if not existing_share:
                # Create a new Share record
                new_share = Share(
                    file_id=f.id,
                    share_token=f.share_token,
                    expires_at=f.share_expires_at,
                    download_limit=None, # Legacy shares had unlimited downloads
                    download_count=0,
                    is_active=True,
                    password_hash=None
                )
                # Note: We do NOT nullify the legacy fields to preserve backward compatibility 
                # as requested, but going forward new logic will use the Share table.
                db.session.add(new_share)
                count += 1
                
        db.session.commit()
        print(f"Migration completed successfully. Migrated {count} legacy share links to the new Share table.")

if __name__ == "__main__":
    migrate()
