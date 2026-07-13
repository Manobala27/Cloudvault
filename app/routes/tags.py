from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Tag, File, Folder, ActivityLog
from app.s3_service import s3_service
from app.services.notification_service import notification_service
import re

tags_bp = Blueprint('tags', __name__, url_prefix='/tags')

@tags_bp.route('/', methods=['GET'])
@login_required
def manage_tags():
    user_tags = Tag.query.filter_by(user_id=current_user.id).order_by(Tag.name.asc()).all()
    return render_template('tags.html', title='Manage Tags', tags=user_tags)

@tags_bp.route('/create', methods=['POST'])
@login_required
def create_tag():
    name = request.form.get('tag_name', '').strip()
    color = request.form.get('tag_color', '#0d6efd').strip()
    
    if not name or len(name) > 50:
        flash("Invalid tag name. Must be 1-50 characters.", "danger")
        return redirect(url_for('tags.manage_tags'))
        
    if not re.match(r'^#[0-9a-fA-F]{6}$', color):
        color = '#0d6efd'
        
    existing = Tag.query.filter_by(user_id=current_user.id, name=name).first()
    if existing:
        flash(f"Tag '{name}' already exists.", "warning")
        return redirect(url_for('tags.manage_tags'))
        
    new_tag = Tag(name=name, color_hex=color, user_id=current_user.id)
    db.session.add(new_tag)
    
    log = ActivityLog(user_id=current_user.id, action='TAG_CREATED', file_name=f"Tag: {name}", ip_address=request.remote_addr)
    db.session.add(log)
    
    db.session.commit()
    flash(f"Tag '{name}' created successfully.", "success")
    return redirect(url_for('tags.manage_tags'))

@tags_bp.route('/delete/<int:tag_id>', methods=['POST'])
@login_required
def delete_tag(tag_id):
    tag = Tag.query.get_or_404(tag_id)
    if tag.user_id != current_user.id:
        flash("Permission denied.", "danger")
        return redirect(url_for('tags.manage_tags'))
        
    name = tag.name
    # SQLAlchemy handles the Many-to-Many association table cleanup due to how we delete it,
    # or because we just delete the tag and the DB handles the relations if configured. 
    # Actually, SQLAlchemy secondary tables will automatically delete the association rows when the parent is deleted.
    db.session.delete(tag)
    
    log = ActivityLog(user_id=current_user.id, action='TAG_DELETED', file_name=f"Tag: {name}", ip_address=request.remote_addr)
    db.session.add(log)
    
    db.session.commit()
    flash(f"Tag '{name}' deleted.", "success")
    return redirect(url_for('tags.manage_tags'))

@tags_bp.route('/assign/file/<int:file_id>', methods=['POST'])
@login_required
def assign_file_tag(file_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.owner != current_user:
        return jsonify({'error': 'Permission denied'}), 403
        
    data = request.get_json()
    tag_id = data.get('tag_id')
    assign = data.get('assign') # True to attach, False to detach
    
    tag = Tag.query.get_or_404(tag_id)
    if tag.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
        
    if assign:
        if tag not in file_record.tags:
            file_record.tags.append(tag)
            log = ActivityLog(user_id=current_user.id, action='ITEM_TAGGED', file_name=f"{file_record.original_filename} (Tag: {tag.name})", ip_address=request.remote_addr)
            db.session.add(log)
            notification_service.create_notification(current_user.id, "Tag Added", f"Added tag '{tag.name}' to '{file_record.original_filename}'.", "TAG_ADDED", "bi-tag-fill")
    else:
        if tag in file_record.tags:
            file_record.tags.remove(tag)
            log = ActivityLog(user_id=current_user.id, action='ITEM_UNTAGGED', file_name=f"{file_record.original_filename} (Tag: {tag.name})", ip_address=request.remote_addr)
            db.session.add(log)
            notification_service.create_notification(current_user.id, "Tag Removed", f"Removed tag '{tag.name}' from '{file_record.original_filename}'.", "TAG_REMOVED", "bi-tag")
            
    db.session.commit()
    return jsonify({'success': True})

@tags_bp.route('/assign/folder/<int:folder_id>', methods=['POST'])
@login_required
def assign_folder_tag(folder_id):
    folder_record = Folder.query.get_or_404(folder_id)
    if folder_record.owner != current_user:
        return jsonify({'error': 'Permission denied'}), 403
        
    data = request.get_json()
    tag_id = data.get('tag_id')
    assign = data.get('assign') 
    
    tag = Tag.query.get_or_404(tag_id)
    if tag.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
        
    if assign:
        if tag not in folder_record.tags:
            folder_record.tags.append(tag)
            log = ActivityLog(user_id=current_user.id, action='ITEM_TAGGED', folder_name=f"{folder_record.name} (Tag: {tag.name})", ip_address=request.remote_addr)
            db.session.add(log)
    else:
        if tag in folder_record.tags:
            folder_record.tags.remove(tag)
            log = ActivityLog(user_id=current_user.id, action='ITEM_UNTAGGED', folder_name=f"{folder_record.name} (Tag: {tag.name})", ip_address=request.remote_addr)
            db.session.add(log)
            
    db.session.commit()
    return jsonify({'success': True})

@tags_bp.route('/view/<int:tag_id>', methods=['GET'])
@login_required
def view_tag(tag_id):
    tag = Tag.query.get_or_404(tag_id)
    if tag.user_id != current_user.id:
        flash("Permission denied.", "danger")
        return redirect(url_for('files.dashboard'))
        
    page = request.args.get('page', 1, type=int)
    
    # Filter files and folders that have this tag, and are not deleted
    file_query = File.query.filter(File.tags.any(id=tag.id), File.owner==current_user, File.is_deleted==False).order_by(File.upload_date.desc())
    folder_query = Folder.query.filter(Folder.tags.any(id=tag.id), Folder.owner==current_user, Folder.is_deleted==False).order_by(Folder.created_at.desc())
    
    folders = folder_query.all()
    files_paginated = file_query.paginate(page=page, per_page=10)
    
    for f in files_paginated.items:
        f.presigned_url = s3_service.generate_presigned_url(f.filename)
        
    return render_template('tag_view.html', title=f"Tag: {tag.name}", tag=tag, files=files_paginated, folders=folders)
