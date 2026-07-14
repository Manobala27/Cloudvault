from app import create_app, db
from app.models import User
app = create_app()
with app.test_client() as client:
    with app.app_context():
        user = User.query.first()
    
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
    
    response = client.get('/upload')
    html = response.data.decode('utf-8')
    print('HTTP Status:', response.status_code)
    print('upload-form in html:', 'id="upload-form"' in html)
    print('file-input in html:', 'id="file-input"' in html)
    print('browse-btn in html:', 'id="browse-btn"' in html)
    
    if 'id="upload-form"' not in html:
        print('Snippet of rendered HTML:')
        print(html[:1500])
