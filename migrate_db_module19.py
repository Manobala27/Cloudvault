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
        # Check if notification table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notification'")
        if cursor.fetchone():
            print("Table 'notification' already exists. Skipping.")
        else:
            cursor.execute("""
            CREATE TABLE notification (
                id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                title VARCHAR(100) NOT NULL,
                message VARCHAR(255) NOT NULL,
                notification_type VARCHAR(50) NOT NULL,
                icon VARCHAR(50),
                is_read BOOLEAN NOT NULL,
                created_at DATETIME NOT NULL,
                action_url VARCHAR(255),
                PRIMARY KEY (id),
                FOREIGN KEY(user_id) REFERENCES user (id)
            )
            """)
            
            cursor.execute("CREATE INDEX ix_notification_user_id ON notification (user_id)")
            print("Table 'notification' created successfully.")
            
        conn.commit()
        print("Module 19 Migration Successful.")
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
