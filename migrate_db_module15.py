import os
import sys
import sqlite3

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db

def migrate():
    app = create_app()
    with app.app_context():
        db_path = os.path.join(app.instance_path, 'site.db')
        
        # Connect directly via sqlite3 for safe ALTER TABLE ADD COLUMN
        print(f"Connecting to database at {db_path}...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns exist first
        cursor.execute("PRAGMA table_info(file)")
        file_columns = [col[1] for col in cursor.fetchall()]
        
        cursor.execute("PRAGMA table_info(folder)")
        folder_columns = [col[1] for col in cursor.fetchall()]
        
        # Add to File
        if 'is_favorite' not in file_columns:
            print("Adding 'is_favorite' to 'file' table...")
            cursor.execute("ALTER TABLE file ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT 0")
        
        if 'favorited_at' not in file_columns:
            print("Adding 'favorited_at' to 'file' table...")
            cursor.execute("ALTER TABLE file ADD COLUMN favorited_at DATETIME")
            
        # Add to Folder
        if 'is_favorite' not in folder_columns:
            print("Adding 'is_favorite' to 'folder' table...")
            cursor.execute("ALTER TABLE folder ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT 0")
            
        if 'favorited_at' not in folder_columns:
            print("Adding 'favorited_at' to 'folder' table...")
            cursor.execute("ALTER TABLE folder ADD COLUMN favorited_at DATETIME")
            
        conn.commit()
        conn.close()
        print("Database migration completed successfully.")

if __name__ == '__main__':
    migrate()
