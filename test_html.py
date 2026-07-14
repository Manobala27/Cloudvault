from html.parser import HTMLParser
from app import create_app, db
from app.models import User

class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found_form = False
        self.found_input = False
    
    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag == 'form' and attr_dict.get('id') == 'upload-form':
            self.found_form = True
        if tag == 'input' and attr_dict.get('id') == 'file-input':
            self.found_input = True

app = create_app()
with app.test_client() as client:
    with app.app_context():
        user = User.query.first()
    
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
    
    response = client.get('/upload')
    html = response.data.decode('utf-8')
    
    parser = FormParser()
    parser.feed(html)
    print("Parsed upload-form:", parser.found_form)
    print("Parsed file-input:", parser.found_input)
