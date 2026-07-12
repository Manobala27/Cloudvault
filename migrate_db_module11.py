import sqlite3
import os
from app import create_app

def migrate():
    app = create_app()
    with app.app_context():
        db_path = os.path.join(app.instance_path, 'site.db')
        print(f"Migrating database at: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create ActivityLog table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action VARCHAR(50) NOT NULL,
            file_name VARCHAR(255),
            folder_name VARCHAR(255),
            ip_address VARCHAR(45),
            created_at DATETIME NOT NULL,
            FOREIGN KEY(user_id) REFERENCES user (id)
        )
        """)
        
        # Create index on user_id for faster queries
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_activity_log_user_id ON activity_log (user_id)
        """)
        
        conn.commit()
        conn.close()
        print("Migration successful: activity_log table created.")

if __name__ == '__main__':
    migrate()
