from app import create_app, db

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Import models so they are known to SQLAlchemy
        from app.models import User
        # Initialize the database.
        db.create_all()
    app.run(debug=True)

