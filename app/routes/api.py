from flask import Blueprint, request, jsonify, g
from functools import wraps
from app.services.api_key_service import api_key_service
from app.models import File, Folder, ActivityLog, Share, Tag
from app import db, limiter
import os
from werkzeug.utils import secure_filename
from app.s3_service import s3_service
from app.models import FileVersion

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'message': 'Missing or invalid Authorization header.'}), 401
            
        raw_key = auth_header.split(' ')[1]
        user = api_key_service.verify_api_key(raw_key)
        
        if not user:
            return jsonify({'success': False, 'message': 'Invalid or expired API Key.'}), 401
            
        if not user.is_active:
            return jsonify({'success': False, 'message': 'Account is disabled.'}), 403
            
        g.api_user = user
        return f(*args, **kwargs)
    return decorated_function

# Apply rate limiting globally to all API routes
limiter.limit("100 per minute")(api_bp)

@api_bp.after_request
def update_key_usage(response):
    if hasattr(g, 'api_user'):
        auth_header = request.headers.get('Authorization')
        if auth_header:
            raw_key = auth_header.split(' ')[1]
            import hashlib
            hashed = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
            from app.models import APIKey
            # Ideally we'd have the APIKey object in `g`, let's just do a quick lookup
            key = APIKey.query.filter_by(api_key_hash=hashed).first()
            if key:
                api_key_service.update_last_used(key.id)
    return response

@api_bp.route('/files', methods=['GET'])
@require_api_key
def get_files():
    folder_id = request.args.get('folder_id', type=int)
    if folder_id:
        folder = Folder.query.filter_by(id=folder_id, user_id=g.api_user.id, is_deleted=False).first()
        if not folder:
            return jsonify({'success': False, 'message': 'Folder not found.'}), 404
        files = File.query.filter_by(user_id=g.api_user.id, folder_id=folder_id, is_deleted=False).all()
    else:
        files = File.query.filter_by(user_id=g.api_user.id, is_deleted=False).all()
        
    return jsonify({
        'success': True,
        'data': [{
            'id': f.id,
            'filename': f.original_filename,
            's3_key': f.filename,
            'file_size': f.file_size,
            'created_at': f.upload_date.isoformat(),
            'folder_id': f.folder_id
        } for f in files]
    })

@api_bp.route('/files/<int:file_id>', methods=['GET'])
@require_api_key
def get_file(file_id):
    file = File.query.filter_by(id=file_id, user_id=g.api_user.id, is_deleted=False).first()
    if not file:
        return jsonify({'success': False, 'message': 'File not found.'}), 404
        
    return jsonify({
        'success': True,
        'data': {
            'id': file.id,
            'filename': file.original_filename,
            's3_key': file.filename,
            'file_size': file.file_size,
            'created_at': file.upload_date.isoformat(),
            'folder_id': file.folder_id,
            'is_favorite': file.is_favorite
        }
    })

@api_bp.route('/upload', methods=['POST'])
@require_api_key
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part.'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file.'}), 400
        
    folder_id = request.form.get('folder_id', type=int)
    
    if file:
        filename = secure_filename(file.filename)
        
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0, os.SEEK_SET)
        
        import uuid
        unique_id = str(uuid.uuid4())
        _, ext = os.path.splitext(filename)
        s3_key = f"user_{g.api_user.id}/{unique_id}{ext}"
        
        content_type = file.content_type
        
        # Using S3 service
        success = s3_service.upload_file(file, s3_key, content_type)
        
        if success:
            new_file = File(
                filename=s3_key,
                original_filename=filename,
                file_size=size,
                user_id=g.api_user.id,
                folder_id=folder_id
            )
            db.session.add(new_file)
            db.session.flush() # flush to get id
            
            new_version = FileVersion(
                file_id=new_file.id,
                version_number=1,
                s3_key=s3_key,
                file_size=size,
                uploaded_by=g.api_user.id,
                is_current=True
            )
            db.session.add(new_version)
            
            log = ActivityLog(user_id=g.api_user.id, action='API_UPLOAD', ip_address=request.remote_addr, details=f"Uploaded {filename} via API")
            db.session.add(log)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'File uploaded successfully.',
                'data': {
                    'id': new_file.id,
                    'filename': new_file.original_filename
                }
            })
        else:
            return jsonify({'success': False, 'message': 'Upload to S3 failed.'}), 500

@api_bp.route('/files/<int:file_id>', methods=['DELETE'])
@require_api_key
def delete_file(file_id):
    file = File.query.filter_by(id=file_id, user_id=g.api_user.id).first()
    if not file:
        return jsonify({'success': False, 'message': 'File not found.'}), 404
        
    if not file.is_deleted:
        file.is_deleted = True
        log = ActivityLog(user_id=g.api_user.id, action='API_DELETE', ip_address=request.remote_addr, details=f"Sent {file.filename} to trash via API")
        db.session.add(log)
        db.session.commit()
        return jsonify({'success': True, 'message': 'File moved to trash.'})
    else:
        # Permanently delete
        s3_service.delete_file(file.s3_key)
        db.session.delete(file)
        log = ActivityLog(user_id=g.api_user.id, action='API_DELETE_PERMANENT', ip_address=request.remote_addr, details=f"Permanently deleted {file.filename} via API")
        db.session.add(log)
        db.session.commit()
        return jsonify({'success': True, 'message': 'File permanently deleted.'})

@api_bp.route('/folders', methods=['GET'])
@require_api_key
def get_folders():
    parent_id = request.args.get('parent_id', type=int)
    if parent_id:
        folders = Folder.query.filter_by(user_id=g.api_user.id, parent_id=parent_id, is_deleted=False).all()
    else:
        folders = Folder.query.filter_by(user_id=g.api_user.id, is_deleted=False).all()
        
    return jsonify({
        'success': True,
        'data': [{
            'id': f.id,
            'name': f.name,
            'parent_id': f.parent_id
        } for f in folders]
    })

@api_bp.route('/folders', methods=['POST'])
@require_api_key
def create_folder():
    data = request.get_json()
    name = data.get('name')
    parent_id = data.get('parent_id')
    
    if not name:
        return jsonify({'success': False, 'message': 'Folder name required.'}), 400
        
    folder = Folder(name=name, user_id=g.api_user.id, parent_id=parent_id)
    db.session.add(folder)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Folder created.',
        'data': {
            'id': folder.id,
            'name': folder.name
        }
    })

@api_bp.route('/search', methods=['GET'])
@require_api_key
def search():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'success': False, 'message': 'Query parameter q required.'}), 400
        
    q_files = File.query.filter_by(user_id=g.api_user.id, is_deleted=False).filter(File.original_filename.ilike(f'%{query}%'))
    q_folders = Folder.query.filter_by(user_id=g.api_user.id, is_deleted=False).filter(Folder.name.ilike(f'%{query}%'))
    
    files = q_files.limit(50).all()
    folders = q_folders.limit(50).all()
    
    log = ActivityLog(user_id=g.api_user.id, action='API_SEARCH', ip_address=request.remote_addr, details=f"Searched via API: {query}")
    db.session.add(log)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'data': {
            'files': [{'id': f.id, 'filename': f.original_filename} for f in files],
            'folders': [{'id': f.id, 'name': f.name} for f in folders]
        }
    })

@api_bp.route('/favorites', methods=['GET'])
@require_api_key
def get_favorites():
    files = File.query.filter_by(user_id=g.api_user.id, is_favorite=True, is_deleted=False).all()
    folders = Folder.query.filter_by(user_id=g.api_user.id, is_favorite=True, is_deleted=False).all()
    
    return jsonify({
        'success': True,
        'data': {
            'files': [{'id': f.id, 'filename': f.filename} for f in files],
            'folders': [{'id': f.id, 'name': f.name} for f in folders]
        }
    })

@api_bp.route('/tags', methods=['GET'])
@require_api_key
def get_tags():
    tags = Tag.query.filter_by(user_id=g.api_user.id).all()
    return jsonify({
        'success': True,
        'data': [{
            'id': t.id,
            'name': t.name,
            'color': t.color
        } for t in tags]
    })

@api_bp.route('/activity', methods=['GET'])
@require_api_key
def get_activity():
    limit = request.args.get('limit', default=50, type=int)
    logs = ActivityLog.query.filter_by(user_id=g.api_user.id).order_by(ActivityLog.timestamp.desc()).limit(limit).all()
    return jsonify({
        'success': True,
        'data': [{
            'id': l.id,
            'action': l.action,
            'details': l.details,
            'timestamp': l.timestamp.isoformat(),
            'ip_address': l.ip_address
        } for l in logs]
    })

@api_bp.route('/versions/<int:file_id>', methods=['GET'])
@require_api_key
def get_versions(file_id):
    file = File.query.filter_by(id=file_id, user_id=g.api_user.id).first()
    if not file:
        return jsonify({'success': False, 'message': 'File not found.'}), 404
        
    versions = file.versions
    return jsonify({
        'success': True,
        'data': [{
            'id': v.id,
            'version_number': v.version_number,
            'created_at': v.created_at.isoformat(),
            'file_size': v.file_size
        } for v in versions]
    })
