import sqlite3
import os

def migrate_module13():
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'site.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}. Please ensure the app has been initialized.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(user)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # 1. Add is_admin
        if 'is_admin' not in columns:
            print("Adding is_admin column to user table...")
            cursor.execute("ALTER TABLE user ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0")
        else:
            print("is_admin column already exists.")

        # 2. Add is_active
        if 'is_active' not in columns:
            print("Adding is_active column to user table...")
            cursor.execute("ALTER TABLE user ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")
        else:
            print("is_active column already exists.")

        # 3. Promote User ID 1 to admin
        print("Promoting User ID 1 to Administrator...")
        cursor.execute("UPDATE user SET is_admin = 1 WHERE id = 1")
        
        conn.commit()
        print("Migration for Module 13 completed successfully.")
        
    except Exception as e:
        print(f"An error occurred during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_module13()
