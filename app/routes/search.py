from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app import db
from app.models import File, Folder, Tag, ActivityLog
from app.s3_service import s3_service
from datetime import datetime, timezone
import json

search_bp = Blueprint('search', __name__, url_prefix='/search')

@search_bp.route('/', methods=['GET'])
@login_required
def advanced_search():
    # Pre-fetch user tags for the filter UI
    user_tags = Tag.query.filter_by(user_id=current_user.id).order_by(Tag.name.asc()).all()
    
    # Render the Advanced Search page (React-like AJAX interface handled via JS in template)
    return render_template('advanced_search.html', title='Advanced Search', user_tags=user_tags)

@search_bp.route('/api', methods=['POST'])
@login_required
def api_search():
    data = request.get_json() or {}
    
    query_text = data.get('query', '').strip()
    item_type = data.get('type', 'all') # 'all', 'files', 'folders'
    is_favorite = data.get('favorite', False)
    tag_ids = data.get('tags', []) # List of tag IDs
    extensions = data.get('extensions', []) # List of extensions like ['.pdf', '.jpg']
    size_min = data.get('size_min') # in bytes
    size_max = data.get('size_max') # in bytes
    date_start = data.get('date_start') # YYYY-MM-DD
    date_end = data.get('date_end') # YYYY-MM-DD
    
    # Optional sorting
    sort_by = data.get('sort', 'newest')

    results = {'files': [], 'folders': []}
    
    # Log the search event if it's an explicit full search, avoid logging every keystroke if possible.
    # The frontend can send a "log_event" flag when the user hits 'Enter' or clicks 'Search' explicitly.
    if data.get('log_event') and (query_text or tag_ids or is_favorite or extensions or size_min or size_max or date_start or date_end):
        log = ActivityLog(user_id=current_user.id, action='ADVANCED_SEARCH_EXECUTED', file_name=f"Query: '{query_text}'", ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()

    # Query Files
    if item_type in ['all', 'files']:
        q_files = File.query.options(joinedload(File.tags), joinedload(File.shares), joinedload(File.versions)).filter_by(owner=current_user, is_deleted=False)
        
        if query_text:
            q_files = q_files.filter(File.original_filename.ilike(f'%{query_text}%'))
            
        if is_favorite:
            q_files = q_files.filter(File.is_favorite == True)
            
        if tag_ids:
            for tag_id in tag_ids:
                q_files = q_files.filter(File.tags.any(Tag.id == tag_id))
                
        if extensions:
            ext_filters = [File.original_filename.ilike(f'%{ext}') for ext in extensions]
            from sqlalchemy import or_
            q_files = q_files.filter(or_(*ext_filters))
            
        if size_min is not None:
            q_files = q_files.filter(File.file_size >= size_min)
            
        if size_max is not None:
            q_files = q_files.filter(File.file_size <= size_max)
            
        if date_start:
            try:
                start_dt = datetime.strptime(date_start, '%Y-%m-%d')
                q_files = q_files.filter(File.upload_date >= start_dt)
            except ValueError:
                pass
                
        if date_end:
            try:
                # Add 1 day to include the end date fully
                import datetime as dt
                end_dt = datetime.strptime(date_end, '%Y-%m-%d') + dt.timedelta(days=1)
                q_files = q_files.filter(File.upload_date < end_dt)
            except ValueError:
                pass
                
        # Sorting
        if sort_by == 'name_asc':
            q_files = q_files.order_by(File.original_filename.asc())
        elif sort_by == 'name_desc':
            q_files = q_files.order_by(File.original_filename.desc())
        elif sort_by == 'oldest':
            q_files = q_files.order_by(File.upload_date.asc())
        else: # newest
            q_files = q_files.order_by(File.upload_date.desc())
            
        # Limit results to avoid massive payloads. Pagination can be added later if needed.
        matched_files = q_files.limit(100).all()
        
        for f in matched_files:
            active_share = next((s for s in f.shares if s.is_active), None)
            max_ver = max((v.version_number for v in f.versions), default=1) if f.versions else 1
            
            results['files'].append({
                'id': f.id,
                'filename': f.original_filename,
                'size': f.file_size,
                'upload_date': f.upload_date.strftime('%Y-%m-%d'),
                'is_favorite': f.is_favorite,
                'tags': [{'id': t.id, 'name': t.name, 'color_hex': t.color_hex} for t in f.tags],
                'has_active_share': active_share is not None,
                'version': max_ver,
                'download_url': f"/download/{f.id}",
                'preview_url': s3_service.generate_presigned_url(f.filename)
            })

    # Query Folders
    if item_type in ['all', 'folders']:
        q_folders = Folder.query.options(joinedload(Folder.tags), joinedload(Folder.files)).filter_by(owner=current_user, is_deleted=False)
        
        if query_text:
            q_folders = q_folders.filter(Folder.name.ilike(f'%{query_text}%'))
            
        if is_favorite:
            q_folders = q_folders.filter(Folder.is_favorite == True)
            
        if tag_ids:
            for tag_id in tag_ids:
                q_folders = q_folders.filter(Folder.tags.any(Tag.id == tag_id))
                
        if date_start:
            try:
                start_dt = datetime.strptime(date_start, '%Y-%m-%d')
                q_folders = q_folders.filter(Folder.created_at >= start_dt)
            except ValueError:
                pass
                
        if date_end:
            try:
                import datetime as dt
                end_dt = datetime.strptime(date_end, '%Y-%m-%d') + dt.timedelta(days=1)
                q_folders = q_folders.filter(Folder.created_at < end_dt)
            except ValueError:
                pass
                
        # Sorting
        if sort_by == 'name_asc':
            q_folders = q_folders.order_by(Folder.name.asc())
        elif sort_by == 'name_desc':
            q_folders = q_folders.order_by(Folder.name.desc())
        elif sort_by == 'oldest':
            q_folders = q_folders.order_by(Folder.created_at.asc())
        else: # newest
            q_folders = q_folders.order_by(Folder.created_at.desc())
            
        matched_folders = q_folders.limit(100).all()
        
        for fld in matched_folders:
            active_files_count = len([f for f in fld.files if not f.is_deleted])
            
            results['folders'].append({
                'id': fld.id,
                'name': fld.name,
                'created_at': fld.created_at.strftime('%Y-%m-%d'),
                'is_favorite': fld.is_favorite,
                'tags': [{'id': t.id, 'name': t.name, 'color_hex': t.color_hex} for t in fld.tags],
                'files_count': active_files_count,
                'url': f"/dashboard?folder_id={fld.id}"
            })

    return jsonify(results)
