import os
import sys

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db

def migrate():
    app = create_app()
    with app.app_context():
        # Because we added entirely new tables (Tag, file_tag, folder_tag),
        # db.create_all() will create them safely without dropping existing tables.
        print("Creating Module 16 new tables (Tag, file_tag, folder_tag)...")
        db.create_all()
        print("Database migration completed successfully.")

if __name__ == '__main__':
    migrate()
