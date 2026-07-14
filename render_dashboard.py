import os
import sys
from app import create_app
from flask import render_template
from unittest.mock import MagicMock

app = create_app()

with app.app_context():
    # Mock current_user
    class MockUser:
        is_authenticated = True
        storage_limit = 10 * 1024 * 1024 * 1024
        id = 1
        has_2fa_enabled = False
        def get_used_space(self): return 1024 * 1024 * 1024
    
    from datetime import datetime
    class MockFile:
        id = 1
        name = "test.txt"
        original_filename = "test.txt"
        size = 1000
        file_size = 1000
        upload_date = datetime.now()
        created_at = datetime.now()
        uploaded_at = datetime.now()
        version = 1
        presigned_url = "http://example.com/test.png"
        shares = []
        tags = []
        def __init__(self):
            pass
            
    class MockFolder:
        id = 1
        name = "Test Folder"
        created_at = datetime.now()
        files = []
        subfolders = []
        color = "#000000"
        tags = []

    class MockPagination:
        items = [MockFile(), MockFile(), MockFile()]
        pages = 1
        page = 1
        has_prev = False
        has_next = False
    
    with app.test_request_context('/dashboard'):
        # Just render dashboard.html
        app.jinja_env.globals['current_user'] = MockUser()
        try:
            html = render_template('dashboard.html', 
                                   folders=[MockFolder(), MockFolder()], 
                                   files=MockPagination(),
                                   used_space=1024*1024*1024,
                                   storage_limit=10 * 1024 * 1024 * 1024,
                                   total_size=1024*1024*1024,
                                   breadcrumbs=[])
            with open('dashboard_test_rendered.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print("Successfully rendered to dashboard_test_rendered.html")
        except Exception as e:
            print("Error:", e)
