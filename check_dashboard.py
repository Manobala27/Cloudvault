from app import create_app, db
from app.models import File, User
import re

app = create_app()
with app.app_context():
    user = User.query.first()
    if user:
        print(f"Testing with user: {user.email}")
        
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
        
    resp = client.get('/dashboard')
    html = resp.data.decode('utf-8')
    
    imgs = re.findall(r'<img[^>]*>', html)
    print(f'Found {len(imgs)} img tags in HTML')
    for img in imgs:
        if 'cv-file-thumbnail' in img:
            print("Thumbnail IMG:", img)
