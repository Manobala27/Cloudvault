from app import create_app, db
import sqlite3
import os

app = create_app()

def migrate():
    with app.app_context():
        db_path = os.path.join(app.instance_path, 'site.db')
        print(f"Migrating database at: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Check if is_deleted exists in file table
            cursor.execute("PRAGMA table_info(file)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'is_deleted' not in columns:
                print("Adding is_deleted and deleted_at to 'file' table...")
                cursor.execute("ALTER TABLE file ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0")
                cursor.execute("ALTER TABLE file ADD COLUMN deleted_at DATETIME")
            else:
                print("'file' table already has is_deleted.")
                
            # Check if is_deleted exists in folder table
            cursor.execute("PRAGMA table_info(folder)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'is_deleted' not in columns:
                print("Adding is_deleted and deleted_at to 'folder' table...")
                cursor.execute("ALTER TABLE folder ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0")
                cursor.execute("ALTER TABLE folder ADD COLUMN deleted_at DATETIME")
            else:
                print("'folder' table already has is_deleted.")
                
            conn.commit()
            print("Migration successful.")
        except Exception as e:
            print(f"Migration failed: {e}")
            conn.rollback()
        finally:
            conn.close()

if __name__ == "__main__":
    migrate()
