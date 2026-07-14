import os
import uuid
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from app import db, bcrypt
from app.models import File, Folder, ActivityLog, Share, FileVersion
from app.s3_service import s3_service
from app.services.notification_service import notification_service
from app.forms import UploadForm

files = Blueprint('files', __name__)

@files.route("/upload", methods=['GET', 'POST'])
@login_required
def upload():
    form = UploadForm()
    
    if request.method == 'POST':
        print("request.files =", request.files, flush=True)
        print("request.form =", request.form, flush=True)
        print("form.errors =", form.errors, flush=True)
        
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if form.validate_on_submit():
        file_obj = form.file.data
        original_filename = secure_filename(file_obj.filename)
        
        # Check size (Max 10MB)
        file_obj.seek(0, os.SEEK_END)
        file_size = file_obj.tell()
        file_obj.seek(0, os.SEEK_SET) # Reset pointer
        
        if file_size > 10 * 1024 * 1024:
            if is_ajax:
                return jsonify({
                    "success": False,
                    "errors": {"file": ["File size exceeds the 10MB limit."]}
                }), 400
            flash("File size exceeds the 10MB limit.", "danger")
            return redirect(url_for('files.upload'))

        # Generate unique key for S3
        unique_id = str(uuid.uuid4())
        _, ext = os.path.splitext(original_filename)
        s3_key = f"user_{current_user.id}/{unique_id}{ext}"
        
        # Upload to S3
        content_type = file_obj.content_type
        success = s3_service.upload_file(file_obj, s3_key, content_type)
        
        if success:
            folder_id_str = request.form.get('folder_id')
            folder_id = int(folder_id_str) if folder_id_str and folder_id_str.isdigit() else None
            
            existing_file = File.query.filter_by(
                owner=current_user,
                folder_id=folder_id,
                original_filename=original_filename,
                is_deleted=False
            ).first()

            if existing_file:
                # Update existing file to point to new version
                existing_file.filename = s3_key
                existing_file.file_size = file_size
                existing_file.upload_date = datetime.now(timezone.utc)
                
                # Demote old versions
                for v in existing_file.versions:
                    v.is_current = False
                    
                max_version = max([v.version_number for v in existing_file.versions] + [0])
                
                new_version = FileVersion(
                    file_id=existing_file.id,
                    version_number=max_version + 1,
                    s3_key=s3_key,
                    file_size=file_size,
                    uploaded_by=current_user.id,
                    is_current=True
                )
                db.session.add(new_version)
                
                log = ActivityLog(user_id=current_user.id, action='VERSION_CREATED', file_name=f"{original_filename} (V{max_version+1})", ip_address=request.remote_addr)
                db.session.add(log)
                db.session.commit()
                
                if not is_ajax:
                    notification_service.create_notification(current_user.id, "Version Created", f"New version of {original_filename} uploaded.", "VERSION_CREATED", "bi-cloud-arrow-up")
                    flash(f"New version of '{original_filename}' uploaded successfully!", "success")
            else:
                # Create new file and version 1
                new_file = File(
                    filename=s3_key,
                    original_filename=original_filename,
                    file_size=file_size,
                    owner=current_user,
                    folder_id=folder_id
                )
                db.session.add(new_file)
                db.session.flush() # get ID
                
                new_version = FileVersion(
                    file_id=new_file.id,
                    version_number=1,
                    s3_key=s3_key,
                    file_size=file_size,
                    uploaded_by=current_user.id,
                    is_current=True
                )
                db.session.add(new_version)
                
                log = ActivityLog(user_id=current_user.id, action='UPLOAD', file_name=original_filename, ip_address=request.remote_addr)
                db.session.add(log)
                db.session.commit()
                
                if not is_ajax:
                    notification_service.create_notification(current_user.id, "Upload Success", f"File '{original_filename}' uploaded successfully.", "UPLOAD_SUCCESS", "bi-check-circle")
                    flash(f"File '{original_filename}' uploaded successfully!", "success")
            
            if is_ajax:
                return jsonify({
                    "success": True,
                    "redirect": url_for("files.dashboard")
                })
            
            return redirect(url_for('files.dashboard'))
        else:
            if is_ajax:
                return jsonify({
                    "success": False,
                    "message": "Failed to upload file to S3."
                }), 500
            
            notification_service.create_notification(current_user.id, "Upload Failed", "Failed to upload file to S3.", "UPLOAD_FAILED", "bi-x-circle")
            flash("Failed to upload file to S3. Please try again.", "danger")
            
    elif request.method == 'POST' and is_ajax:
        return jsonify({
            "success": False,
            "errors": form.errors
        }), 400

    return render_template('upload.html', title='Upload File', form=form)

@files.route("/dashboard")
@login_required
def dashboard():
    print("ENTER dashboard()", flush=True)
    try:
        page = request.args.get('page', 1, type=int)
        search_query = request.args.get('search', '')
        sort_by = request.args.get('sort', 'newest')
        folder_id_str = request.args.get('folder_id')
        
        current_folder = None
        folder_id = None
        if folder_id_str and folder_id_str.isdigit():
            folder_id = int(folder_id_str)
            current_folder = Folder.query.get_or_404(folder_id)
            if current_folder.owner != current_user:
                flash("You don't have permission to view this folder.", "danger")
                return redirect(url_for('files.dashboard'))

        from sqlalchemy.orm import joinedload
        
        # Base query for current user's files and folders
        file_query = File.query.options(joinedload(File.tags)).filter_by(owner=current_user, is_deleted=False)
        folder_query = Folder.query.options(joinedload(Folder.tags)).filter_by(owner=current_user, is_deleted=False)

        if search_query:
            file_query = file_query.filter(File.original_filename.ilike(f'%{search_query}%'))
            folder_query = folder_query.filter(Folder.name.ilike(f'%{search_query}%'))
            # When searching, ignore folder hierarchy to show all matches
        else:
            file_query = file_query.filter_by(folder_id=folder_id)
            folder_query = folder_query.filter_by(parent_id=folder_id)

        # Sorting logic
        if sort_by == 'oldest':
            file_query = file_query.order_by(File.upload_date.asc())
            folder_query = folder_query.order_by(Folder.created_at.asc())
        elif sort_by == 'name_asc':
            file_query = file_query.order_by(File.original_filename.asc())
            folder_query = folder_query.order_by(Folder.name.asc())
        elif sort_by == 'name_desc':
            file_query = file_query.order_by(File.original_filename.desc())
            folder_query = folder_query.order_by(Folder.name.desc())
        else:
            file_query = file_query.order_by(File.upload_date.desc()) # default 'newest'
            folder_query = folder_query.order_by(Folder.created_at.desc())

        # We paginate files, but typically show all folders for the current view.
        # To keep UI simple, we'll just fetch all subfolders for this page.
        folders = folder_query.all()
        files_paginated = file_query.paginate(page=page, per_page=10)

        # Calculate stats
        all_files = File.query.filter_by(owner=current_user).all()
        total_files = len(all_files)
        
        # Calculate total size including all historical versions
        from app.models import FileVersion
        all_versions = FileVersion.query.filter_by(uploaded_by=current_user.id).all()
        total_size = sum(v.file_size for v in all_versions)

        # Generate presigned URLs for preview/download for current page items
        for f in files_paginated.items:
            f.presigned_url = s3_service.generate_presigned_url(f.filename)

        # Breadcrumbs
        breadcrumbs = []
        if current_folder:
            curr = current_folder
            while curr:
                breadcrumbs.insert(0, curr)
                curr = curr.parent
                
        # Pre-fetch all tags for this user so we can render them in the assign modal
        from app.models import Tag
        user_tags = Tag.query.filter_by(user_id=current_user.id).order_by(Tag.name.asc()).all()
        
        print("EXIT dashboard()", flush=True)
        return render_template('dashboard.html',
                               title='Dashboard',
                               files=files_paginated,
                               folders=folders,
                               current_folder=current_folder,
                               breadcrumbs=breadcrumbs,
                               search_query=search_query,
                               sort_by=sort_by,
                               total_files=total_files,
                               total_size=total_size,
                               user_tags=user_tags)
    except Exception:
        import traceback
        print("\n========== DASHBOARD ERROR ==========", flush=True)
        traceback.print_exc()
        print("=====================================\n", flush=True)
        raise

@files.route("/download/<int:file_id>")
@login_required
def download(file_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.owner != current_user:
        flash("You don't have permission to download this file.", "danger")
        return redirect(url_for('files.dashboard', folder_id=file_record.folder_id))
    
    url = s3_service.generate_presigned_url(
        file_record.filename, 
        download_filename=file_record.original_filename
    )
    
    if url:
        # Log Download
        log = ActivityLog(user_id=current_user.id, action='DOWNLOAD', file_name=file_record.original_filename, ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        return redirect(url)
    else:
        flash("Failed to generate download link.", "danger")
        return redirect(url_for('files.dashboard', folder_id=file_record.folder_id))

@files.route("/delete/<int:file_id>", methods=['POST'])
@login_required
def delete_file(file_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.owner != current_user:
        flash("You don't have permission to delete this file.", "danger")
        return redirect(url_for('files.dashboard', folder_id=file_record.folder_id))

    folder_id = file_record.folder_id
    file_record.is_deleted = True
    file_record.deleted_at = datetime.now(timezone.utc)
    
    # Log Delete
    log = ActivityLog(user_id=current_user.id, action='DELETE', file_name=file_record.original_filename, ip_address=request.remote_addr)
    db.session.add(log)
    
    db.session.commit()
    notification_service.create_notification(current_user.id, "File Trashed", f"'{file_record.original_filename}' moved to trash.", "FILE_DELETED", "bi-trash")
    flash(f"File '{file_record.original_filename}' has been moved to Trash.", "success")
    return redirect(url_for('files.dashboard', folder_id=folder_id))

@files.route("/share/toggle/<int:file_id>", methods=['POST'])
@login_required
def toggle_share(file_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.owner != current_user:
        flash("You don't have permission to modify this file.", "danger")
        return redirect(url_for('files.dashboard', folder_id=file_record.folder_id))

    action = request.form.get('share_action', 'create')
    
    # Check if there is an existing active share
    active_share = next((s for s in file_record.shares if s.is_active), None)

    if action == 'revoke':
        if active_share:
            active_share.is_active = False
            
            # Log Revoke Share
            log = ActivityLog(user_id=current_user.id, action='REVOKE_SHARE', file_name=file_record.original_filename, ip_address=request.remote_addr)
            db.session.add(log)
            flash(f"Share link revoked for '{file_record.original_filename}'.", "info")
            db.session.commit()
    else:
        # Create a new share (and disable the old one if it exists, to ensure 1 active share per file via Dashboard for now)
        if active_share:
            active_share.is_active = False
            
        password_plain = request.form.get('share_password')
        expiry_days = request.form.get('share_expiry', '7')
        download_limit_str = request.form.get('share_limit', 'unlimited')
        
        password_hash = None
        if password_plain:
            password_hash = bcrypt.generate_password_hash(password_plain).decode('utf-8')
            
        expires_at = None
        if expiry_days.isdigit():
            expires_at = datetime.now(timezone.utc) + timedelta(days=int(expiry_days))
            
        download_limit = None
        if download_limit_str.isdigit():
            download_limit = int(download_limit_str)
            
        new_share = Share(
            file_id=file_record.id,
            share_token=str(uuid.uuid4()),
            password_hash=password_hash,
            expires_at=expires_at,
            download_limit=download_limit,
            download_count=0,
            is_active=True
        )
        db.session.add(new_share)
        
        # Log Share Created
        log = ActivityLog(user_id=current_user.id, action='SHARE_CREATED', file_name=file_record.original_filename, ip_address=request.remote_addr)
        db.session.add(log)
        
        notification_service.create_notification(current_user.id, "File Shared", f"Created share link for '{file_record.original_filename}'.", "FILE_SHARED", "bi-share")
        
        flash(f"Public link created for '{file_record.original_filename}'.", "success")
        db.session.commit()
        
    return redirect(url_for('files.dashboard', folder_id=file_record.folder_id))

@files.route("/shared/<share_token>", methods=['GET', 'POST'])
def shared_file(share_token):
    # Find the share record
    share_record = Share.query.filter_by(share_token=share_token).first_or_404()
    file_record = share_record.file
    
    if not share_record.is_active or file_record.is_deleted:
        flash("This share link is invalid, expired, or has been revoked.", "danger")
        return render_template('404.html'), 404
        
    # Check expiration
    if share_record.expires_at:
        expires_at_aware = share_record.expires_at.replace(tzinfo=timezone.utc) if share_record.expires_at.tzinfo is None else share_record.expires_at
        if expires_at_aware < datetime.now(timezone.utc):
            share_record.is_active = False
            
            # Log Expiration if we know the owner
            log = ActivityLog(user_id=file_record.owner.id, action='SHARE_EXPIRED', file_name=file_record.original_filename, ip_address=request.remote_addr)
            db.session.add(log)
            db.session.commit()
            
            flash("This share link has expired.", "danger")
            return render_template('403.html'), 403

    # Check limits
    if share_record.download_limit and share_record.download_count >= share_record.download_limit:
        share_record.is_active = False
        db.session.commit()
        flash("This share link has reached its download limit.", "danger")
        return render_template('403.html'), 403

    # Log Share Opened (only on GET to avoid spam on failed passwords)
    if request.method == 'GET':
        log = ActivityLog(user_id=file_record.owner.id, action='SHARE_OPENED', file_name=file_record.original_filename, ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()

    # Password Protection Logic
    if share_record.password_hash:
        if request.method == 'POST':
            entered_password = request.form.get('share_password')
            if not entered_password or not bcrypt.check_password_hash(share_record.password_hash, entered_password):
                log = ActivityLog(user_id=file_record.owner.id, action='SHARE_PASSWORD_FAILED', file_name=file_record.original_filename, ip_address=request.remote_addr)
                db.session.add(log)
                db.session.commit()
                flash("Incorrect password.", "danger")
                return render_template('shared_password.html', share=share_record)
        else:
            return render_template('shared_password.html', share=share_record)

    # Generate a temporary presigned URL for the public user to download/preview
    download_url = url_for('files.public_download', share_token=share_token, _external=True)
    preview_url = s3_service.generate_presigned_url(
        file_record.filename, 
        expiration=3600, 
        download_filename=file_record.original_filename
    )
    
    if not preview_url:
        flash("Failed to retrieve file from storage.", "danger")
        return render_template('404.html'), 404
        
    return render_template('shared_file.html', file=file_record, share=share_record, download_url=download_url, preview_url=preview_url)

@files.route("/shared/<share_token>/download", methods=['POST', 'GET'])
def public_download(share_token):
    share_record = Share.query.filter_by(share_token=share_token).first_or_404()
    file_record = share_record.file
    
    if not share_record.is_active or file_record.is_deleted:
        flash("This share link is invalid, expired, or has been revoked.", "danger")
        return render_template('403.html'), 403
        
    # Check expiration
    if share_record.expires_at:
        expires_at_aware = share_record.expires_at.replace(tzinfo=timezone.utc) if share_record.expires_at.tzinfo is None else share_record.expires_at
        if expires_at_aware < datetime.now(timezone.utc):
            share_record.is_active = False
            
            # Log Expiration if we know the owner
            log = ActivityLog(user_id=file_record.owner.id, action='SHARE_EXPIRED', file_name=file_record.original_filename, ip_address=request.remote_addr)
            db.session.add(log)
            db.session.commit()
            
            flash("This share link has expired.", "danger")
            return render_template('403.html'), 403

    # Password protection requires POST with session or token, but since this is direct download link,
    # if it's password protected and a GET request is made, redirect to the main share page.
    if request.method != 'POST' and share_record.password_hash:
        return redirect(url_for('files.shared_file', share_token=share_token))

    # Check limits
    if share_record.download_limit:
        if share_record.download_count >= share_record.download_limit:
            share_record.is_active = False
            db.session.commit()
            flash("This share link has reached its download limit.", "danger")
            return render_template('403.html'), 403
            
    # Increment download count
    share_record.download_count += 1
    if share_record.download_limit and share_record.download_count >= share_record.download_limit:
        share_record.is_active = False
        # Log expiration due to limit
        log_expire = ActivityLog(user_id=file_record.owner.id, action='SHARE_EXPIRED', file_name=file_record.original_filename, ip_address=request.remote_addr)
        db.session.add(log_expire)
        
    # Log Download
    log = ActivityLog(user_id=file_record.owner.id, action='SHARE_DOWNLOADED', file_name=file_record.original_filename, ip_address=request.remote_addr)
    db.session.add(log)
    
    db.session.commit()
    
    # Redirect to actual S3 presigned URL
    s3_url = s3_service.generate_presigned_url(
        file_record.filename, 
        expiration=60, # very short lived
        download_filename=file_record.original_filename
    )
    return redirect(s3_url)

@files.route("/folder/create", methods=['POST'])
@login_required
def create_folder():
    folder_name = request.form.get('folder_name', '').strip()
    parent_id_str = request.form.get('parent_id')
    
    parent_id = int(parent_id_str) if parent_id_str and parent_id_str.isdigit() else None

    if not folder_name:
        flash("Folder name cannot be empty.", "danger")
        return redirect(url_for('files.dashboard', folder_id=parent_id))
        
    new_folder = Folder(name=folder_name, owner=current_user, parent_id=parent_id)
    db.session.add(new_folder)
    
    # Log Folder Create
    log = ActivityLog(user_id=current_user.id, action='CREATE_FOLDER', folder_name=folder_name, ip_address=request.remote_addr)
    db.session.add(log)
    
    db.session.commit()
    
    flash(f"Folder '{folder_name}' created successfully.", "success")
    return redirect(url_for('files.dashboard', folder_id=parent_id))

def _delete_folder_recursive(folder):
    """Recursively delete a folder and all its contents from DB and S3."""
    # Delete all files in this folder
    for f in folder.files:
        s3_service.delete_file(f.filename)
        db.session.delete(f)
        
    # Recursively delete subfolders
    for sub in folder.subfolders:
        _delete_folder_recursive(sub)
        
    # Delete the folder itself
    db.session.delete(folder)

def _soft_delete_folder_recursive(folder):
    """Recursively soft delete a folder and all its contents."""
    for f in folder.files:
        if not f.is_deleted:
            f.is_deleted = True
            f.deleted_at = datetime.now(timezone.utc)
            
    for sub in folder.subfolders:
        if not sub.is_deleted:
            _soft_delete_folder_recursive(sub)
            
    folder.is_deleted = True
    folder.deleted_at = datetime.now(timezone.utc)

@files.route("/folder/delete/<int:folder_id>", methods=['POST'])
@login_required
def delete_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    if folder.owner != current_user:
        flash("You don't have permission to delete this folder.", "danger")
        return redirect(url_for('files.dashboard', folder_id=folder.parent_id))
        
    parent_id = folder.parent_id
    folder_name = folder.name
    
    _soft_delete_folder_recursive(folder)
    
    # Log Folder Delete
    log = ActivityLog(user_id=current_user.id, action='DELETE_FOLDER', folder_name=folder_name, ip_address=request.remote_addr)
    db.session.add(log)
    
    db.session.commit()
    
    flash(f"Folder '{folder_name}' has been moved to Trash.", "success")
    return redirect(url_for('files.dashboard', folder_id=parent_id))

@files.route("/trash")
@login_required
def trash():
    # 30-day cleanup
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
    
    # SQLite might not perfectly handle timezone-aware comparison depending on driver setup,
    # so we'll fetch and compare in python for safety or use simple filter
    # Actually, SQLite dates are strings, let's fetch all deleted and filter in Python to be perfectly timezone safe.
    deleted_files_all = File.query.filter_by(owner=current_user, is_deleted=True).all()
    
    for f in deleted_files_all:
        if f.deleted_at:
            aware_deleted = f.deleted_at.replace(tzinfo=timezone.utc) if f.deleted_at.tzinfo is None else f.deleted_at
            if aware_deleted < cutoff_date:
                s3_service.delete_file(f.filename)
                db.session.delete(f)
                
    deleted_folders_all = Folder.query.filter_by(owner=current_user, is_deleted=True).all()
    for f in deleted_folders_all:
        if f.deleted_at:
            aware_deleted = f.deleted_at.replace(tzinfo=timezone.utc) if f.deleted_at.tzinfo is None else f.deleted_at
            if aware_deleted < cutoff_date:
                # the files inside this folder are already picked up by deleted_files_all since recursive delete sets deleted_at
                db.session.delete(f)
                
    db.session.commit()
    
    deleted_files = File.query.filter_by(owner=current_user, is_deleted=True).order_by(File.deleted_at.desc()).all()
    deleted_folders = Folder.query.filter_by(owner=current_user, is_deleted=True).order_by(Folder.deleted_at.desc()).all()
    
    return render_template('trash.html', title='Trash', files=deleted_files, folders=deleted_folders)

@files.route("/restore/file/<int:file_id>", methods=['POST'])
@login_required
def restore_file(file_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.owner != current_user:
        flash("Permission denied.", "danger")
        return redirect(url_for('files.trash'))
        
    file_record.is_deleted = False
    file_record.deleted_at = None
    
    # Safe restore: if original folder is deleted or missing, move to root
    if file_record.folder_id:
        parent = Folder.query.get(file_record.folder_id)
        if not parent or parent.is_deleted:
            file_record.folder_id = None
            flash(f"Original folder was deleted. '{file_record.original_filename}' restored to Home.", "warning")
        else:
            flash(f"'{file_record.original_filename}' restored successfully.", "success")
    else:
        flash(f"'{file_record.original_filename}' restored successfully.", "success")
        
    # Log Restore
    log = ActivityLog(user_id=current_user.id, action='RESTORE', file_name=file_record.original_filename, ip_address=request.remote_addr)
    db.session.add(log)
    
    notification_service.create_notification(current_user.id, "File Restored", f"'{file_record.original_filename}' restored from trash.", "FILE_RESTORED", "bi-bootstrap-reboot")
        
    db.session.commit()
    return redirect(url_for('files.trash'))

@files.route("/restore/folder/<int:folder_id>", methods=['POST'])
@login_required
def restore_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    if folder.owner != current_user:
        flash("Permission denied.", "danger")
        return redirect(url_for('files.trash'))
        
    def _restore_recursive(fld):
        fld.is_deleted = False
        fld.deleted_at = None
        for f in fld.files:
            f.is_deleted = False
            f.deleted_at = None
        for sub in fld.subfolders:
            _restore_recursive(sub)
            
    _restore_recursive(folder)
    
    if folder.parent_id:
        parent = Folder.query.get(folder.parent_id)
        if not parent or parent.is_deleted:
            folder.parent_id = None
            flash(f"Parent folder was deleted. '{folder.name}' restored to Home.", "warning")
        else:
            flash(f"Folder '{folder.name}' restored successfully.", "success")
    else:
        flash(f"Folder '{folder.name}' restored successfully.", "success")
        
    # Log Restore Folder
    log = ActivityLog(user_id=current_user.id, action='RESTORE_FOLDER', folder_name=folder.name, ip_address=request.remote_addr)
    db.session.add(log)
        
    db.session.commit()
    return redirect(url_for('files.trash'))

@files.route("/delete_permanent/file/<int:file_id>", methods=['POST'])
@login_required
def delete_permanent_file(file_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.owner != current_user:
        flash("Permission denied.", "danger")
        return redirect(url_for('files.trash'))
        
    # Delete all versions from S3
    for v in file_record.versions:
        s3_service.delete_file(v.s3_key)
        
    # Fallback delete just in case
    s3_service.delete_file(file_record.filename)
    
    # Log Permanent Delete File
    log = ActivityLog(user_id=current_user.id, action='PERMANENT_DELETE', file_name=file_record.original_filename, ip_address=request.remote_addr)
    db.session.add(log)
    log_v = ActivityLog(user_id=current_user.id, action='VERSION_DELETED', file_name=file_record.original_filename, ip_address=request.remote_addr)
    db.session.add(log_v)
    
    db.session.delete(file_record)
    db.session.commit()
    flash(f"'{file_record.original_filename}' and all its versions permanently deleted.", "success")
    return redirect(url_for('files.trash'))

@files.route("/delete_permanent/folder/<int:folder_id>", methods=['POST'])
@login_required
def delete_permanent_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    if folder.owner != current_user:
        flash("Permission denied.", "danger")
        return redirect(url_for('files.trash'))
        
    _delete_folder_recursive(folder)
    
    # Log Permanent Delete Folder
    log = ActivityLog(user_id=current_user.id, action='PERMANENT_DELETE_FOLDER', folder_name=folder.name, ip_address=request.remote_addr)
    db.session.add(log)
    
    db.session.commit()
    flash(f"Folder '{folder.name}' permanently deleted.", "success")
    return redirect(url_for('files.trash'))

@files.route("/shares")
@login_required
def shared_dashboard():
    # Fetch all shares (both active and inactive) for current user's files
    user_shares = Share.query.join(File).filter(File.user_id == current_user.id, File.is_deleted == False).order_by(Share.created_at.desc()).all()
    return render_template('shares.html', title='Shared Files', shares=user_shares)

@files.route("/shares/<int:share_id>/revoke", methods=['POST'])
@login_required
def revoke_specific_share(share_id):
    share = Share.query.get_or_404(share_id)
    if share.file.owner != current_user:
        flash("Permission denied.", "danger")
        return redirect(url_for('files.shared_dashboard'))
        
    share.is_active = False
    log = ActivityLog(user_id=current_user.id, action='REVOKE_SHARE', file_name=share.file.original_filename, ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    
    flash("Share link revoked successfully.", "success")
    return redirect(url_for('files.shared_dashboard'))

@files.route("/restore_version/<int:file_id>/<int:version_id>", methods=['POST'])
@login_required
def restore_version(file_id, version_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.owner != current_user:
        flash("Permission denied.", "danger")
        return redirect(url_for('files.dashboard', folder_id=file_record.folder_id))
        
    version = FileVersion.query.get_or_404(version_id)
    if version.file_id != file_record.id:
        flash("Invalid version.", "danger")
        return redirect(url_for('files.dashboard', folder_id=file_record.folder_id))
        
    if version.is_current:
        flash("This version is already the current version.", "info")
        return redirect(url_for('files.dashboard', folder_id=file_record.folder_id))
        
    # Generate new S3 key
    unique_id = str(uuid.uuid4())
    _, ext = os.path.splitext(file_record.original_filename)
    new_s3_key = f"user_{current_user.id}/{unique_id}{ext}"
    
    # Copy S3 object
    success = s3_service.copy_file(version.s3_key, new_s3_key)
    if not success:
        flash("Failed to restore version from storage.", "danger")
        return redirect(url_for('files.dashboard', folder_id=file_record.folder_id))
        
    # Demote old versions
    for v in file_record.versions:
        v.is_current = False
        
    # Create new version representing the restoration
    max_version = max([v.version_number for v in file_record.versions] + [0])
    new_version_num = max_version + 1
    
    new_version = FileVersion(
        file_id=file_record.id,
        version_number=new_version_num,
        s3_key=new_s3_key,
        file_size=version.file_size,
        uploaded_by=current_user.id,
        is_current=True
    )
    db.session.add(new_version)
    
    # Update main file
    file_record.filename = new_s3_key
    file_record.file_size = version.file_size
    file_record.upload_date = datetime.now(timezone.utc)
    
    # Log Activity
    log = ActivityLog(user_id=current_user.id, action='VERSION_RESTORED', file_name=f"{file_record.original_filename} (V{new_version_num} from V{version.version_number})", ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    
    notification_service.create_notification(current_user.id, "Version Restored", f"Restored {file_record.original_filename} to V{version.version_number}.", "VERSION_RESTORED", "bi-clock-history")

    flash(f"Version {version.version_number} of '{file_record.original_filename}' restored successfully.", "success")
    return redirect(url_for('files.dashboard', folder_id=file_record.folder_id))

@files.route("/download_version/<int:version_id>")
@login_required
def download_version(version_id):
    version = FileVersion.query.get_or_404(version_id)
    if version.file.owner != current_user:
        flash("Permission denied.", "danger")
        return redirect(url_for('files.dashboard'))
        
    url = s3_service.generate_presigned_url(
        version.s3_key, 
        download_filename=version.file.original_filename
    )
    
    if url:
        log = ActivityLog(user_id=current_user.id, action='VERSION_DOWNLOADED', file_name=f"{version.file.original_filename} (V{version.version_number})", ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        return redirect(url)
    else:
        flash("Failed to generate download link for version.", "danger")
        return redirect(url_for('files.dashboard'))

@files.route("/favorite/file/<int:file_id>", methods=['POST'])
@login_required
def toggle_favorite_file(file_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.owner != current_user:
        return jsonify({'error': 'Permission denied'}), 403
        
    file_record.is_favorite = not file_record.is_favorite
    file_record.favorited_at = datetime.now(timezone.utc) if file_record.is_favorite else None
    
    action = 'FAVORITE_ADDED' if file_record.is_favorite else 'FAVORITE_REMOVED'
    log = ActivityLog(user_id=current_user.id, action=action, file_name=file_record.original_filename, ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    
    if is_fav:
        notification_service.create_notification(current_user.id, "Favorite Added", f"'{file_record.original_filename}' favorited.", "FAVORITE_ADDED", "bi-star-fill")
    else:
        notification_service.create_notification(current_user.id, "Favorite Removed", f"'{file_record.original_filename}' unfavorited.", "FAVORITE_REMOVED", "bi-star")
    
    return jsonify({'success': True, 'is_favorite': file_record.is_favorite})

@files.route("/favorite/folder/<int:folder_id>", methods=['POST'])
@login_required
def toggle_favorite_folder(folder_id):
    folder_record = Folder.query.get_or_404(folder_id)
    if folder_record.owner != current_user:
        return jsonify({'error': 'Permission denied'}), 403
        
    folder_record.is_favorite = not folder_record.is_favorite
    folder_record.favorited_at = datetime.now(timezone.utc) if folder_record.is_favorite else None
    
    action = 'FAVORITE_ADDED' if folder_record.is_favorite else 'FAVORITE_REMOVED'
    log = ActivityLog(user_id=current_user.id, action=action, folder_name=folder_record.name, ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    
    return jsonify({'success': True, 'is_favorite': folder_record.is_favorite})

@files.route("/favorites")
@login_required
def favorites():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort', 'recently_favorited')
    
    file_query = File.query.filter_by(owner=current_user, is_deleted=False, is_favorite=True)
    folder_query = Folder.query.filter_by(owner=current_user, is_deleted=False, is_favorite=True)
    
    if search_query:
        file_query = file_query.filter(File.original_filename.ilike(f'%{search_query}%'))
        folder_query = folder_query.filter(Folder.name.ilike(f'%{search_query}%'))
        
    if sort_by == 'oldest':
        file_query = file_query.order_by(File.upload_date.asc())
        folder_query = folder_query.order_by(Folder.created_at.asc())
    elif sort_by == 'name_asc':
        file_query = file_query.order_by(File.original_filename.asc())
        folder_query = folder_query.order_by(Folder.name.asc())
    elif sort_by == 'name_desc':
        file_query = file_query.order_by(File.original_filename.desc())
        folder_query = folder_query.order_by(Folder.name.desc())
    elif sort_by == 'recently_favorited':
        file_query = file_query.order_by(File.favorited_at.desc())
        folder_query = folder_query.order_by(Folder.favorited_at.desc())
    else: # newest
        file_query = file_query.order_by(File.upload_date.desc())
        folder_query = folder_query.order_by(Folder.created_at.desc())
        
    folders = folder_query.all()
    files_paginated = file_query.paginate(page=page, per_page=10)
    
    for f in files_paginated.items:
        f.presigned_url = s3_service.generate_presigned_url(f.filename)
        
    return render_template('favorites.html', title='Favorites',
                           files=files_paginated,
                           folders=folders,
                           search_query=search_query,
                           sort_by=sort_by)

@files.route("/preview/<int:file_id>")
@login_required
def preview(file_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.owner != current_user:
        flash("You don't have permission to view this file.", "danger")
        return redirect(url_for('files.dashboard', folder_id=file_record.folder_id))
    
    # Get previous and next files in the same folder for navigation
    folder_files = File.query.filter_by(folder_id=file_record.folder_id, owner=current_user, is_deleted=False).order_by(File.original_filename.asc()).all()
    
    prev_file = None
    next_file = None
    for i, f in enumerate(folder_files):
        if f.id == file_record.id:
            if i > 0:
                prev_file = folder_files[i-1]
            if i < len(folder_files) - 1:
                next_file = folder_files[i+1]
            break
            
    # Determine file type
    filename = file_record.original_filename.lower()
    
    image_exts = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')
    video_exts = ('.mp4', '.mov', '.webm')
    audio_exts = ('.mp3', '.wav', '.ogg')
    pdf_ext = ('.pdf',)
    text_exts = ('.txt', '.json', '.csv', '.log', '.py', '.js', '.html', '.css', '.md', '.xml', '.yml', '.yaml')
    
    file_type = 'unsupported'
    text_content = None
    
    if filename.endswith(image_exts):
        file_type = 'image'
    elif filename.endswith(video_exts):
        file_type = 'video'
    elif filename.endswith(audio_exts):
        file_type = 'audio'
    elif filename.endswith(pdf_ext):
        file_type = 'pdf'
    elif filename.endswith(text_exts):
        if file_record.file_size <= 2 * 1024 * 1024:  # <= 2MB
            file_type = 'text'
            raw_bytes = s3_service.get_file_content(file_record.filename)
            if raw_bytes:
                try:
                    text_content = raw_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    file_type = 'unsupported' # Fallback if not utf-8
        else:
            # Over 2MB -> unsupported -> forces download
            file_type = 'unsupported'

    presigned_url = s3_service.generate_presigned_url(file_record.filename)
    
    # Log Activity
    log = ActivityLog(user_id=current_user.id, action='PREVIEW_OPENED', file_name=file_record.original_filename, ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    
    return render_template('preview.html', 
                           title=f'Preview {file_record.original_filename}',
                           file=file_record,
                           file_type=file_type,
                           presigned_url=presigned_url,
                           text_content=text_content,
                           prev_file=prev_file,
                           next_file=next_file)

@files.route("/shared/<share_token>/preview", methods=['GET', 'POST'])
def shared_preview(share_token):
    from app.models import Share
    share_record = Share.query.filter_by(share_token=share_token).first_or_404()
    
    if not share_record.is_active:
        flash("This shared link has expired or been revoked.", "danger")
        return redirect(url_for('auth.login'))
        
    if share_record.password_hash:
        if request.method == 'GET':
            if not session.get(f'share_auth_{share_token}'):
                # Redirect back to the auth page
                return redirect(url_for('files.shared_file', share_token=share_token))
        elif request.method == 'POST':
            from app import bcrypt
            pwd = request.form.get('password')
            if not pwd or not bcrypt.check_password_hash(share_record.password_hash, pwd):
                flash("Incorrect password.", "danger")
                return redirect(url_for('files.shared_file', share_token=share_token))
            session[f'share_auth_{share_token}'] = True
    
    file_record = share_record.file
    
    # Determine file type
    filename = file_record.original_filename.lower()
    image_exts = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')
    video_exts = ('.mp4', '.mov', '.webm')
    audio_exts = ('.mp3', '.wav', '.ogg')
    pdf_ext = ('.pdf',)
    text_exts = ('.txt', '.json', '.csv', '.log', '.py', '.js', '.html', '.css', '.md', '.xml', '.yml', '.yaml')
    
    file_type = 'unsupported'
    text_content = None
    
    if filename.endswith(image_exts):
        file_type = 'image'
    elif filename.endswith(video_exts):
        file_type = 'video'
    elif filename.endswith(audio_exts):
        file_type = 'audio'
    elif filename.endswith(pdf_ext):
        file_type = 'pdf'
    elif filename.endswith(text_exts):
        if file_record.file_size <= 2 * 1024 * 1024:  # <= 2MB
            file_type = 'text'
            raw_bytes = s3_service.get_file_content(file_record.filename)
            if raw_bytes:
                try:
                    text_content = raw_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    file_type = 'unsupported' # Fallback if not utf-8
        else:
            file_type = 'unsupported'

    presigned_url = s3_service.generate_presigned_url(file_record.filename)
    
    return render_template('preview.html', 
                           title=f'Preview {file_record.original_filename}',
                           file=file_record,
                           file_type=file_type,
                           presigned_url=presigned_url,
                           text_content=text_content,
                           prev_file=None,
                           next_file=None,
                           is_shared=True,
                           share_token=share_token)
