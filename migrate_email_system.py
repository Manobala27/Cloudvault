import sys
from app import create_app, db
from sqlalchemy import text

def run_migration():
    print("--- STARTING EMAIL SYSTEM DATABASE MIGRATION ---")
    app = create_app()
    with app.app_context():
        # Columns to add with their DDL types (Postgres and SQLite compatible)
        columns = [
            ("email_verified", "BOOLEAN DEFAULT FALSE"),
            ("pending_new_email", "VARCHAR(120) NULL"),
            ("pref_welcome_email", "BOOLEAN DEFAULT TRUE"),
            ("pref_share_emails", "BOOLEAN DEFAULT TRUE"),
            ("pref_login_alerts", "BOOLEAN DEFAULT TRUE"),
            ("pref_storage_alerts", "BOOLEAN DEFAULT TRUE"),
            ("pref_security_alerts", "BOOLEAN DEFAULT TRUE"),
            ("pref_product_updates", "BOOLEAN DEFAULT TRUE"),
            ("failed_login_attempts", "INTEGER DEFAULT 0"),
            ("highest_storage_alert_sent", "INTEGER DEFAULT 0")
        ]
        
        # Add columns
        for col_name, col_type in columns:
            try:
                db.session.execute(text(f'ALTER TABLE "user" ADD COLUMN {col_name} {col_type}'))
                db.session.commit()
                print(f"[OK] Added column: {col_name}")
            except Exception as e:
                db.session.rollback()
                print(f"[INFO] Skipping column {col_name} (it may already exist): {e}")
                
        # Set existing users as verified
        try:
            db.session.execute(text('UPDATE "user" SET email_verified = TRUE WHERE email_verified IS NULL OR email_verified = FALSE'))
            db.session.commit()
            print("[OK] Existing users initialized to email_verified = TRUE.")
        except Exception as e:
            db.session.rollback()
            # If column type was BOOLEAN, check if setting it directly without quotes is fine (it is)
            print(f"[ERROR] Failed to update existing users: {e}")
            
        # Ensure default preferences are set to true for existing users
        pref_updates = [
            "pref_welcome_email = TRUE",
            "pref_share_emails = TRUE",
            "pref_login_alerts = TRUE",
            "pref_storage_alerts = TRUE",
            "pref_security_alerts = TRUE",
            "pref_product_updates = TRUE",
            "failed_login_attempts = 0",
            "highest_storage_alert_sent = 0"
        ]
        for update in pref_updates:
            try:
                db.session.execute(text(f'UPDATE "user" SET {update} WHERE {update.split(" = ")[0]} IS NULL'))
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"[ERROR] Failed to set default for {update}: {e}")

    print("--- EMAIL SYSTEM DATABASE MIGRATION COMPLETE ---")

if __name__ == "__main__":
    run_migration()
