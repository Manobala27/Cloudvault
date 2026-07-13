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
        
        # We might need to add the new ones if they don't exist
        if 'trusted_device_token' not in columns:
            cursor.execute("ALTER TABLE user ADD COLUMN trusted_device_token VARCHAR(255)")
        if 'trusted_device_expiry' not in columns:
            cursor.execute("ALTER TABLE user ADD COLUMN trusted_device_expiry DATETIME")
        if 'last_2fa_used' not in columns:
            cursor.execute("ALTER TABLE user ADD COLUMN last_2fa_used DATETIME")
            
        conn.commit()
        print("Module 21 DB Updated Successfully.")
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
