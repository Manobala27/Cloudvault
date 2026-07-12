import sqlite3

def migrate():
    try:
        conn = sqlite3.connect('c:/Users/balam/OneDrive/Documents/CloudVault/instance/site.db')
        c = conn.cursor()
        
        # Create folder table
        try:
            c.execute('''
                CREATE TABLE folder (
                    id INTEGER NOT NULL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    created_at DATETIME NOT NULL,
                    user_id INTEGER NOT NULL,
                    parent_id INTEGER,
                    FOREIGN KEY(user_id) REFERENCES user (id),
                    FOREIGN KEY(parent_id) REFERENCES folder (id)
                )
            ''')
            print("Created folder table")
        except sqlite3.OperationalError as e:
            print(f"folder table might already exist: {e}")
            
        # Add folder_id column to file table
        try:
            c.execute('ALTER TABLE file ADD COLUMN folder_id INTEGER REFERENCES folder(id)')
            print("Added folder_id column to file table")
        except sqlite3.OperationalError as e:
            print(f"folder_id column might already exist: {e}")
            
        conn.commit()
        conn.close()
        print("Module 8 Migration complete.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    migrate()
