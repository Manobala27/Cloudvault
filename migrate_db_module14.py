import os
from app import create_app, db
from app.models import File, FileVersion

app = create_app()

with app.app_context():
    print("Creating new tables...")
    db.create_all()
    
    print("Migrating existing files to FileVersion...")
    files = File.query.all()
    migrated_count = 0
    
    for f in files:
        # Check if version already exists
        existing_version = FileVersion.query.filter_by(file_id=f.id).first()
        if not existing_version:
            v1 = FileVersion(
                file_id=f.id,
                version_number=1,
                s3_key=f.filename,
                file_size=f.file_size,
                uploaded_at=f.upload_date,
                uploaded_by=f.user_id,
                is_current=True
            )
            db.session.add(v1)
            migrated_count += 1
            
    db.session.commit()
    print(f"Successfully migrated {migrated_count} files to Version 1.")
    print("Migration Module 14 complete.")
