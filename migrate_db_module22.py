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
        # Create api_key table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_key (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name VARCHAR(100) NOT NULL,
                api_key_hash VARCHAR(255) NOT NULL,
                last_used DATETIME,
                expires_at DATETIME,
                created_at DATETIME NOT NULL,
                is_active BOOLEAN NOT NULL,
                FOREIGN KEY(user_id) REFERENCES user(id)
            )
        ''')
            
        conn.commit()
        print("Module 22 DB Migration Successful.")
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
