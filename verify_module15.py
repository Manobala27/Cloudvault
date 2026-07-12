import os
import sys
import io

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db, bcrypt
from app.models import User, File, Folder, ActivityLog

def verify_module15():
    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        with app.app_context():
            print("--- MODULE 15 VERIFICATION ---")
            
            # Setup Users
            u1 = User.query.filter_by(email='admin@cloudvault.com').first()
            u2 = User.query.filter_by(email='user2@cloudvault.com').first()
            
            # Login as Admin
            client.post('/login', data={'email': 'admin@cloudvault.com', 'password': 'password123'}, follow_redirects=True)
            
            # Create a file
            data = {'file': (io.BytesIO(b"Hello Fav"), 'FavDoc.txt')}
            client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
            
            # Create a folder
            client.post('/folder/create', data={'folder_name': 'FavFolder'}, follow_redirects=True)
            
            f = File.query.filter_by(original_filename='FavDoc.txt', owner=u1).order_by(File.id.desc()).first()
            fld = Folder.query.filter_by(name='FavFolder', owner=u1).order_by(Folder.id.desc()).first()
            
            if not f or not fld:
                print("Setup Failed")
                return
                
            # 1. Favorite a file
            res = client.post(f'/favorite/file/{f.id}')
            data_file = res.get_json()
            if data_file and data_file.get('success') and data_file.get('is_favorite'):
                print("1. Favorite a file (AJAX): OK")
            else:
                print("1. Favorite a file: FAIL")
                
            # 2. Favorite a folder
            res = client.post(f'/favorite/folder/{fld.id}')
            data_folder = res.get_json()
            if data_folder and data_folder.get('success') and data_folder.get('is_favorite'):
                print("2. Favorite a folder (AJAX): OK")
            else:
                print("2. Favorite a folder: FAIL")
                
            # 3. Check Favorites page
            res = client.get('/favorites')
            if b'FavDoc.txt' in res.data and b'FavFolder' in res.data:
                print("3. Favorites page displays starred items: OK")
            else:
                print("3. Favorites page displays starred items: FAIL")
                
            # 4. Search in Favorites
            res = client.get('/favorites?search=FavDoc')
            if b'FavDoc.txt' in res.data and b'FavFolder' not in res.data:
                print("4. Search in Favorites: OK")
            else:
                print("4. Search in Favorites: FAIL")
                
            # 5. Sorting in Favorites (recently_favorited)
            res = client.get('/favorites?sort=recently_favorited')
            if res.status_code == 200:
                print("5. Sorting (recently_favorited): OK")
            else:
                print("5. Sorting (recently_favorited): FAIL")
                
            # 6. Unfavorite item
            res = client.post(f'/favorite/file/{f.id}')
            data_file = res.get_json()
            if data_file and data_file.get('success') and not data_file.get('is_favorite'):
                print("6. Unfavorite item (AJAX): OK")
            else:
                print("6. Unfavorite item: FAIL")
                
            res = client.get('/favorites')
            if b'FavDoc.txt' not in res.data:
                print("7. Favorites page respects unfavorite: OK")
            else:
                print("7. Favorites page respects unfavorite: FAIL")
                
            # 8. Activity Logs
            logs = ActivityLog.query.filter_by(user_id=u1.id).order_by(ActivityLog.id.desc()).limit(15).all()
            actions = [l.action for l in logs]
            if 'FAVORITE_ADDED' in actions and 'FAVORITE_REMOVED' in actions:
                print("8. Activity Logs (FAVORITE_ADDED, FAVORITE_REMOVED): OK")
            else:
                print("8. Activity Logs: FAIL")
                
            # 9. Security (Ownership check)
            client.get('/logout', follow_redirects=True)
            client.post('/login', data={'email': 'user2@cloudvault.com', 'password': 'password123'}, follow_redirects=True)
            
            res = client.post(f'/favorite/folder/{fld.id}')
            if res.status_code == 403:
                print("9. Security Ownership validation: OK")
            else:
                print("9. Security Ownership validation: FAIL", res.status_code)
                
            print("--- MODULE 15 VERIFICATION COMPLETE ---")

if __name__ == '__main__':
    verify_module15()
