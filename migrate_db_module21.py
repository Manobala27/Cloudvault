import sqlite3
import os
import sys

def migrate():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'site.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        sys.exit(1)
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(user)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'two_factor_enabled' in columns:
            print("Columns already exist. Skipping migration.")
        else:
            cursor.execute("ALTER TABLE user ADD COLUMN two_factor_enabled BOOLEAN NOT NULL DEFAULT 0")
            cursor.execute("ALTER TABLE user ADD COLUMN two_factor_secret VARCHAR(32)")
            cursor.execute("ALTER TABLE user ADD COLUMN backup_codes TEXT")
            cursor.execute("ALTER TABLE user ADD COLUMN trusted_device_until DATETIME")
            
            conn.commit()
            print("Module 21 Migration Successful.")
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
