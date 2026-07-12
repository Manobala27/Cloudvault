from app import create_app, db
from app.models import Share, File
from flask import render_template

app = create_app()

with app.app_context():
    # Let's get the first share
    share = Share.query.first()
    if share:
        # Mock request context
        with app.test_request_context('/shared/' + share.share_token):
            html = render_template('shared_file.html', file=share.file, share=share, download_url='/dl', preview_url='/prev')
            print(html)
    else:
        print("No share found")
