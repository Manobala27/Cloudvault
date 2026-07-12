import sqlite3

def migrate():
    try:
        conn = sqlite3.connect('c:/Users/balam/OneDrive/Documents/CloudVault/instance/site.db')
        c = conn.cursor()
        
        # Add share_token column
        try:
            c.execute('ALTER TABLE file ADD COLUMN share_token VARCHAR(36)')
            print("Added share_token column")
        except sqlite3.OperationalError as e:
            print(f"share_token column might already exist: {e}")
            
        # Add share_expires_at column
        try:
            c.execute('ALTER TABLE file ADD COLUMN share_expires_at DATETIME')
            print("Added share_expires_at column")
        except sqlite3.OperationalError as e:
            print(f"share_expires_at column might already exist: {e}")
            
        conn.commit()
        conn.close()
        print("Migration complete.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    migrate()
