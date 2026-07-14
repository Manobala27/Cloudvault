from app import create_app
app = create_app()
with app.test_client() as client:
    response = client.get('/upload')
    html = response.data.decode('utf-8')
    print('upload-form in html:', 'id="upload-form"' in html)
    print('file-input in html:', 'id="file-input"' in html)
    print('browse-btn in html:', 'id="browse-btn"' in html)
    if 'id="upload-form"' not in html:
        print('HTTP Status:', response.status_code)
        print('Redirect Location:', response.headers.get('Location'))
        print('Snippet:')
        print(html[:1000])
