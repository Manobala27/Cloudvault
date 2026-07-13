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
        # Create backup table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                backup_name VARCHAR(100) NOT NULL,
                backup_type VARCHAR(20) NOT NULL,
                backup_size INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'completed',
                storage_path VARCHAR(255) NOT NULL,
                FOREIGN KEY(user_id) REFERENCES user(id)
            )
        ''')
            
        conn.commit()
        print("Module 23 DB Migration Successful.")
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
