import io
import os
import shutil
import ctypes
import threading
import mimetypes
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, render_template, url_for, flash, redirect, request, abort, jsonify, send_file
from sqlalchemy import func, desc, or_
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from app import db, bcrypt
from app.models import User, File, Folder, Share, ActivityLog, FileVersion, Notification
from app.s3_service import s3_service
from app.services.analytics_service import analytics_service
from app.services.settings_service import settings_service
from flask_login import current_user, login_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# ==========================================================================
# ADMIN DASHBOARD HOME
# ==========================================================================
@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    verified_users = User.query.filter_by(email_verified=True).count()
    unverified_users = User.query.filter_by(email_verified=False).count()
    active_users = User.query.filter_by(is_active=True).count()
    
    total_files = File.query.filter_by(is_deleted=False).count()
    total_folders = Folder.query.filter_by(is_deleted=False).count()
    shared_files = Share.query.filter_by(is_active=True).count()
    favorites = File.query.filter_by(is_favorite=True, is_deleted=False).count() + Folder.query.filter_by(is_favorite=True, is_deleted=False).count()
    trash_items = File.query.filter_by(is_deleted=True).count() + Folder.query.filter_by(is_deleted=True).count()
    
    # Calculate storage
    all_versions = FileVersion.query.all()
    total_storage_used = sum(v.file_size for v in all_versions)
    avg_storage_per_user = total_storage_used / total_users if total_users > 0 else 0
    
    total_activity_logs = ActivityLog.query.count()
    
    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        verified_users=verified_users,
        unverified_users=unverified_users,
        active_users=active_users,
        total_files=total_files,
        total_folders=total_folders,
        shared_files=shared_files,
        favorites=favorites,
        trash_items=trash_items,
        total_storage_used=total_storage_used,
        avg_storage_per_user=avg_storage_per_user,
        total_activity_logs=total_activity_logs
    )

# ==========================================================================
# ANALYTICS VISUALIZATION
# ==========================================================================
@admin_bp.route("/analytics", methods=['GET'])
@login_required
@admin_required
def analytics():
    log = ActivityLog(user_id=current_user.id, action='ADMIN_ANALYTICS_VIEWED', ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    return render_template('admin/admin_analytics.html')

@admin_bp.route("/analytics/data", methods=['GET'])
@login_required
@admin_required
def analytics_data():
    data = analytics_service.get_admin_analytics()
    return jsonify(data)

# ==========================================================================
# USER MANAGEMENT & PROFILE
# ==========================================================================
@admin_bp.route("/users")
@login_required
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    role_filter = request.args.get('role', '').strip()
    sort_by = request.args.get('sort', 'id_asc').strip()
    
    query = User.query
    if search_query:
        query = query.filter((User.username.ilike(f"%{search_query}%")) | (User.email.ilike(f"%{search_query}%")))
        
    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'disabled':
        query = query.filter_by(is_active=False)
        
    if role_filter == 'admin':
        query = query.filter_by(is_admin=True)
    elif role_filter == 'user':
        query = query.filter_by(is_admin=False)
        
    if sort_by == 'username_asc':
        query = query.order_by(User.username.asc())
    elif sort_by == 'username_desc':
        query = query.order_by(User.username.desc())
    elif sort_by == 'registered_desc':
        query = query.order_by(User.date_registered.desc())
    else:
        query = query.order_by(User.id.asc())
        
    users_paginated = query.paginate(page=page, per_page=10)
    
    # Calculate storage per user
    for u in users_paginated.items:
        u_versions = FileVersion.query.filter_by(uploaded_by=u.id).all()
        u._total_storage = sum(v.file_size for v in u_versions)
    
    return render_template(
        'admin/users.html',
        users=users_paginated,
        search_query=search_query,
        status_filter=status_filter,
        role_filter=role_filter,
        sort_by=sort_by
    )

@admin_bp.route("/users/<int:user_id>")
@login_required
@admin_required
def user_profile(user_id):
    user = User.query.get_or_404(user_id)
    
    # Storage details
    u_versions = FileVersion.query.filter_by(uploaded_by=user.id).all()
    storage_used = sum(v.file_size for v in u_versions)
    
    files_count = File.query.filter_by(user_id=user.id, is_deleted=False).count()
    folders_count = Folder.query.filter_by(user_id=user.id, is_deleted=False).count()
    favorites_count = File.query.filter_by(user_id=user.id, is_favorite=True, is_deleted=False).count() + Folder.query.filter_by(user_id=user.id, is_favorite=True, is_deleted=False).count()
    
    shares_count = Share.query.join(File).filter(File.user_id == user.id, Share.is_active == True).count()
    
    recent_activity = ActivityLog.query.filter_by(user_id=user.id).order_by(ActivityLog.created_at.desc()).limit(10).all()
    
    return render_template(
        'admin/user_profile.html',
        user=user,
        storage_used=storage_used,
        files_count=files_count,
        folders_count=folders_count,
        favorites_count=favorites_count,
        shares_count=shares_count,
        recent_activity=recent_activity
    )

@admin_bp.route("/users/bulk", methods=['POST'])
@login_required
@admin_required
def bulk_users():
    user_ids = request.form.getlist('user_ids')
    action = request.form.get('bulk_action')
    
    if not user_ids or not action:
        flash("No users or action selected.", "warning")
        return redirect(url_for('admin.users'))
        
    count = 0
    for uid in user_ids:
        uid_int = int(uid)
        if uid_int == current_user.id:
            continue
        user = User.query.get(uid_int)
        if not user:
            continue
            
        if action == 'activate':
            user.is_active = True
            log = ActivityLog(user_id=current_user.id, action='ADMIN_ACTIVATE_USER', file_name=user.username, ip_address=request.remote_addr)
            db.session.add(log)
            count += 1
        elif action == 'deactivate':
            if user.is_admin:
                admin_count = User.query.filter_by(is_admin=True, is_active=True).count()
                if admin_count <= 1:
                    continue
            user.is_active = False
            log = ActivityLog(user_id=current_user.id, action='ADMIN_DISABLE_USER', file_name=user.username, ip_address=request.remote_addr)
            db.session.add(log)
            count += 1
        elif action == 'verify_email':
            user.email_verified = True
            log = ActivityLog(user_id=current_user.id, action='ADMIN_VERIFY_EMAIL', file_name=user.username, ip_address=request.remote_addr)
            db.session.add(log)
            count += 1
        elif action == 'reset_password':
            # Set a generic random password and prompt reset (we'll generate temporary pwd)
            temp_pwd = bcrypt.generate_password_hash("TempPass123!").decode('utf-8')
            user.password = temp_pwd
            log = ActivityLog(user_id=current_user.id, action='ADMIN_RESET_PASSWORD', file_name=user.username, ip_address=request.remote_addr)
            db.session.add(log)
            count += 1
            
    db.session.commit()
    flash(f"Bulk action '{action}' applied to {count} users.", "success")
    return redirect(url_for('admin.users'))

@admin_bp.route("/users/<int:user_id>/toggle_status", methods=['POST'])
@login_required
@admin_required
def toggle_status(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot disable your own account.", "danger")
        return redirect(url_for('admin.users'))
        
    if user.is_admin and user.is_active:
        admin_count = User.query.filter_by(is_admin=True, is_active=True).count()
        if admin_count <= 1:
            flash("You cannot disable the last active administrator.", "danger")
            return redirect(url_for('admin.users'))
            
    user.is_active = not user.is_active
    action = 'ADMIN_ACTIVATE_USER' if user.is_active else 'ADMIN_DISABLE_USER'
    
    log = ActivityLog(user_id=current_user.id, action=action, file_name=user.username, ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    
    status = "enabled" if user.is_active else "disabled"
    flash(f"User {user.username} has been {status}.", "success")
    return redirect(url_for('admin.users'))

@admin_bp.route("/users/<int:user_id>/toggle_admin", methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot demote yourself.", "danger")
        return redirect(url_for('admin.users'))
        
    user.is_admin = not user.is_admin
    action = 'ADMIN_PROMOTE_ADMIN' if user.is_admin else 'ADMIN_REMOVE_ADMIN'
    
    log = ActivityLog(user_id=current_user.id, action=action, file_name=user.username, ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    
    role = "promoted to Admin" if user.is_admin else "removed from Admin role"
    flash(f"User {user.username} has been {role}.", "success")
    return redirect(url_for('admin.users'))

@admin_bp.route("/users/<int:user_id>/delete", methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for('admin.users'))
        
    if user.is_admin:
        admin_count = User.query.filter_by(is_admin=True).count()
        if admin_count <= 1:
            flash("You cannot delete the last administrator.", "danger")
            return redirect(url_for('admin.users'))
            
    files = File.query.filter_by(user_id=user.id).all()
    for f in files:
        for v in f.versions:
            try: s3_service.delete_file(v.s3_key)
            except Exception: pass
        try: s3_service.delete_file(f.filename)
        except Exception: pass
        
    file_ids = [f.id for f in files]
    if file_ids:
        Share.query.filter(Share.file_id.in_(file_ids)).delete(synchronize_session=False)
    ActivityLog.query.filter_by(user_id=user.id).delete()
    File.query.filter_by(user_id=user.id).delete()
    Folder.query.filter_by(user_id=user.id).delete()
    
    username = user.username
    db.session.delete(user)
    
    log = ActivityLog(user_id=current_user.id, action='ADMIN_DELETE_USER', file_name=username, ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    
    flash(f"User {username} and all associated data have been permanently deleted.", "success")
    return redirect(url_for('admin.users'))

# ==========================================================================
# STORAGE MANAGEMENT
# ==========================================================================
@admin_bp.route("/storage")
@login_required
@admin_required
def storage():
    users = User.query.all()
    total_storage = settings_service.get('storage_limit_gb') * 1024 * 1024 * 1024 * len(users)
    
    all_versions = FileVersion.query.all()
    storage_used = sum(v.file_size for v in all_versions)
    free_storage = max(total_storage - storage_used, 0)
    
    # Calculate storage per user
    user_storages = []
    for u in users:
        u_versions = [v for v in all_versions if v.uploaded_by == u.id]
        u_size = sum(v.file_size for v in u_versions)
        user_storages.append((u, u_size))
        
    top_consumers = sorted(user_storages, key=lambda x: x[1], reverse=True)[:5]
    unused_accounts = [u for u, size in user_storages if size == 0]
    
    # Large files (> 5MB)
    large_files = File.query.filter_by(is_deleted=False).filter(File.file_size > 5 * 1024 * 1024).order_by(File.file_size.desc()).limit(10).all()
    
    # Largest folders
    folders = Folder.query.filter_by(is_deleted=False).all()
    folder_sizes = []
    for f in folders:
        f_files = File.query.filter_by(folder_id=f.id, is_deleted=False).all()
        f_size = sum(fl.file_size for fl in f_files if fl.file_size)
        folder_sizes.append((f, f_size))
    largest_folders = sorted(folder_sizes, key=lambda x: x[1], reverse=True)[:5]
    
    return render_template(
        'admin/storage.html',
        total_storage=total_storage,
        storage_used=storage_used,
        free_storage=free_storage,
        top_consumers=top_consumers,
        unused_accounts=unused_accounts,
        large_files=large_files,
        largest_folders=largest_folders
    )

# ==========================================================================
# FILE MANAGEMENT
# ==========================================================================
@admin_bp.route("/files")
@login_required
@admin_required
def files():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    user_filter = request.args.get('user', '').strip()
    ext_filter = request.args.get('ext', '').strip()
    status_filter = request.args.get('status', 'active').strip()
    
    query = File.query
    if status_filter == 'deleted':
        query = query.filter_by(is_deleted=True)
    else:
        query = query.filter_by(is_deleted=False)
        
    if search_query:
        query = query.filter(File.original_filename.ilike(f"%{search_query}%"))
        
    if user_filter:
        query = query.join(User).filter(User.username.ilike(f"%{user_filter}%"))
        
    if ext_filter:
        query = query.filter(File.original_filename.ilike(f"%.{ext_filter}"))
        
    files_paginated = query.order_by(File.upload_date.desc()).paginate(page=page, per_page=15)
    
    return render_template(
        'admin/files.html',
        files=files_paginated,
        search_query=search_query,
        user_filter=user_filter,
        ext_filter=ext_filter,
        status_filter=status_filter
    )

@admin_bp.route("/files/<int:file_id>/delete", methods=['POST'])
@login_required
@admin_required
def admin_delete_file(file_id):
    file = File.query.get_or_404(file_id)
    filename = file.original_filename
    
    # Soft or Hard Delete (Admin can soft-delete or permanently purge from Trash view)
    is_hard = request.form.get('hard_delete') == 'true'
    
    if is_hard or file.is_deleted:
        # Permanent delete from AWS S3
        for v in file.versions:
            try: s3_service.delete_file(v.s3_key)
            except Exception: pass
        try: s3_service.delete_file(file.filename)
        except Exception: pass
        
        db.session.delete(file)
        action = 'ADMIN_HARD_DELETE_FILE'
    else:
        file.is_deleted = True
        file.deleted_at = datetime.now(timezone.utc)
        action = 'ADMIN_SOFT_DELETE_FILE'
        
    log = ActivityLog(user_id=current_user.id, action=action, file_name=filename, ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    
    flash(f"File {filename} has been deleted.", "success")
    return redirect(url_for('admin.files', status='deleted' if (is_hard or file.is_deleted) else 'active'))

@admin_bp.route("/files/<int:file_id>/restore", methods=['POST'])
@login_required
@admin_required
def admin_restore_file(file_id):
    file = File.query.get_or_404(file_id)
    file.is_deleted = False
    file.deleted_at = None
    
    log = ActivityLog(user_id=current_user.id, action='ADMIN_RESTORE_FILE', file_name=file.original_filename, ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    
    flash(f"File {file.original_filename} restored successfully.", "success")
    return redirect(url_for('admin.files', status='active'))

@admin_bp.route("/files/<int:file_id>/download")
@login_required
@admin_required
def admin_download_file(file_id):
    file = File.query.get_or_404(file_id)
    
    # Try S3 download
    s3_key = file.filename
    # check if has current version
    current_ver = next((v for v in file.versions if v.is_current), None)
    if current_ver:
        s3_key = current_ver.s3_key
        
    file_data = s3_service.get_file_content(s3_key)
    if not file_data:
        flash("Could not download file from S3.", "danger")
        return redirect(url_for('admin.files'))
        
    return send_file(
        io.BytesIO(file_data),
        download_name=file.original_filename,
        as_attachment=True
    )

# ==========================================================================
# SYSTEM HEALTH
# ==========================================================================
@admin_bp.route("/health")
@login_required
@admin_required
def health():
    # Database check
    try:
        db.session.execute(db.text('SELECT 1'))
        db_status = 'Healthy'
    except Exception as e:
        db_status = f'Error: {str(e)}'
        
    # AWS S3 check
    s3_success, s3_message = s3_service.verify_connection()
    s3_status = 'Healthy' if s3_success else f'Error: {s3_message}'
    
    # SMTP check
    smtp_host = settings_service.get('smtp_host')
    smtp_port = settings_service.get('smtp_port')
    if smtp_host:
        import smtplib
        try:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=5)
            server.noop()
            server.quit()
            smtp_status = 'Healthy'
        except Exception as e:
            smtp_status = f'Error: {str(e)}'
    else:
        smtp_status = 'Not Configured (Standard Mailer Active)'
        
    # OS / Disk / Memory checks
    import platform
    import flask
    python_ver = platform.python_version()
    flask_ver = flask.__version__
    
    total_d, used_d, free_d = shutil.disk_usage('.')
    disk_total = f"{total_d / (1024**3):.2f} GB"
    disk_used = f"{used_d / (1024**3):.2f} GB ({used_d/total_d*100:.1f}%)"
    
    # Windows native memory check using ctypes to avoid psutil dependency
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ('dwLength', ctypes.c_ulong),
                ('dwMemoryLoad', ctypes.c_ulong),
                ('ullTotalPhys', ctypes.c_uint64),
                ('ullAvailPhys', ctypes.c_uint64),
                ('ullTotalPageFile', ctypes.c_uint64),
                ('ullAvailPageFile', ctypes.c_uint64),
                ('ullTotalVirtual', ctypes.c_uint64),
                ('ullAvailVirtual', ctypes.c_uint64),
                ('ullAvailExtendedVirtual', ctypes.c_uint64),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        mem_total = f"{stat.ullTotalPhys / (1024**3):.2f} GB"
        mem_used = f"{(stat.ullTotalPhys - stat.ullAvailPhys) / (1024**3):.2f} GB ({stat.dwMemoryLoad}%)"
    except Exception:
        mem_total = "N/A"
        mem_used = "N/A"
        
    # Active Background Threads
    bg_threads = [t.name for t in threading.enumerate()]
    
    return render_template(
        'admin/health.html',
        db_status=db_status,
        s3_status=s3_status,
        smtp_status=smtp_status,
        disk_total=disk_total,
        disk_used=disk_used,
        mem_total=mem_total,
        mem_used=mem_used,
        python_ver=python_ver,
        flask_ver=flask_ver,
        bg_threads=bg_threads
    )

# ==========================================================================
# ACTIVITY MONITOR & AUDIT LOGS
# ==========================================================================
@admin_bp.route("/activity")
@login_required
@admin_required
def activity():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    action_filter = request.args.get('action', '').strip()
    
    query = ActivityLog.query
    if search_query:
        query = query.join(User).filter(User.username.ilike(f"%{search_query}%"))
    if action_filter:
        query = query.filter_by(action=action_filter)
        
    logs = query.order_by(ActivityLog.created_at.desc()).paginate(page=page, per_page=20)
    
    # Get distinct action types for filter dropdown
    actions_list = [r[0] for r in db.session.query(ActivityLog.action).distinct().all()]
    
    return render_template(
        'admin/activity.html',
        logs=logs,
        search_query=search_query,
        action_filter=action_filter,
        actions_list=actions_list
    )

@admin_bp.route("/audit_logs")
@login_required
@admin_required
def audit_logs():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    
    # Immutable admin action query (filter prefix 'ADMIN_')
    query = ActivityLog.query.filter(ActivityLog.action.like('ADMIN_%'))
    if search_query:
        query = query.join(User).filter(User.username.ilike(f"%{search_query}%"))
        
    logs = query.order_by(ActivityLog.created_at.desc()).paginate(page=page, per_page=20)
    
    return render_template(
        'admin/audit_logs.html',
        logs=logs,
        search_query=search_query
    )

# ==========================================================================
# SETTINGS PANEL
# ==========================================================================
@admin_bp.route("/settings", methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    if request.method == 'POST':
        settings_service.update({
            'upload_limit_mb': request.form.get('upload_limit_mb'),
            'storage_limit_gb': request.form.get('storage_limit_gb'),
            'allowed_extensions': request.form.get('allowed_extensions'),
            'maintenance_mode': 'maintenance_mode' in request.form,
            'registration_enabled': 'registration_enabled' in request.form,
            'email_verification_required': 'email_verification_required' in request.form,
            'password_min_length': request.form.get('password_min_length'),
            'smtp_host': request.form.get('smtp_host'),
            'smtp_port': request.form.get('smtp_port'),
            'smtp_user': request.form.get('smtp_user'),
            'smtp_password': request.form.get('smtp_password'),
            'smtp_default_sender': request.form.get('smtp_default_sender')
        })
        
        log = ActivityLog(user_id=current_user.id, action='ADMIN_SETTINGS_CHANGED', ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        
        flash("Application settings saved successfully.", "success")
        return redirect(url_for('admin.settings'))
        
    return render_template('admin/settings.html', current_settings=settings_service.get_all())

# ==========================================================================
# REPORT COMPILING & EXPORT
# ==========================================================================
@admin_bp.route("/reports")
@login_required
@admin_required
def reports():
    return render_template('admin/reports.html')

@admin_bp.route("/reports/export/<string:report_type>/<string:export_format>")
@login_required
@admin_required
def export_report(report_type, export_format):
    # Retrieve report dataset based on type
    dataset = []
    headers = []
    title_str = ""
    
    if report_type == 'users':
        title_str = "CloudVault User Directory"
        headers = ["ID", "Username", "Email", "Verified", "Active", "Registered"]
        users_list = User.query.all()
        for u in users_list:
            dataset.append([
                u.id, u.username, u.email,
                "Yes" if u.email_verified else "No",
                "Yes" if u.is_active else "No",
                u.date_registered.strftime('%Y-%m-%d')
            ])
    elif report_type == 'storage':
        title_str = "CloudVault Storage Audit Report"
        headers = ["User", "Email", "Storage Used (Bytes)", "Files Count"]
        users_list = User.query.all()
        for u in users_list:
            u_versions = FileVersion.query.filter_by(uploaded_by=u.id).all()
            size = sum(v.file_size for v in u_versions)
            f_count = File.query.filter_by(user_id=u.id, is_deleted=False).count()
            dataset.append([u.username, u.email, size, f_count])
    elif report_type == 'uploads':
        title_str = "CloudVault Upload Statistics"
        headers = ["File Name", "Uploader", "Size (Bytes)", "Upload Date", "Status"]
        files_list = File.query.all()
        for f in files_list:
            dataset.append([
                f.original_filename, f.owner.username if f.owner else 'Deleted',
                f.file_size, f.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
                "Deleted" if f.is_deleted else "Active"
            ])
    else:  # activity
        title_str = "CloudVault Activity Logs"
        headers = ["Log ID", "User", "Action", "File Target", "IP Address", "Timestamp"]
        logs_list = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(100).all()
        for lg in logs_list:
            dataset.append([
                lg.id, lg.user.username if lg.user else 'System',
                lg.action, lg.file_name or '', lg.ip_address or '',
                lg.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])

    # Export formats: CSV, Excel, PDF
    if export_format == 'csv':
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(dataset)
        
        output_bytes = io.BytesIO(output.getvalue().encode('utf-8'))
        return send_file(
            output_bytes,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"cloudvault_{report_type}_report.csv"
        )
        
    elif export_format == 'excel':
        wb = Workbook()
        ws = wb.active
        ws.title = report_type.capitalize()
        ws.append(headers)
        for row in dataset:
            ws.append(row)
        
        out_stream = io.BytesIO()
        wb.save(out_stream)
        out_stream.seek(0)
        
        return send_file(
            out_stream,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"cloudvault_{report_type}_report.xlsx"
        )
        
    elif export_format == 'pdf':
        out_stream = io.BytesIO()
        doc = SimpleDocTemplate(out_stream, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        story.append(Paragraph(title_str, styles['Title']))
        story.append(Spacer(1, 15))
        
        # Build report table
        table_data = [headers] + dataset[:50]  # Limit to first 50 rows in PDF for readability
        t = Table(table_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#3B82F6")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 10),
            ('BOTTOMPADDING', (0,0), (-1,0), 8),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#f8fafc")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('FONTSIZE', (0,1), (-1,-1), 8),
        ]))
        story.append(t)
        doc.build(story)
        out_stream.seek(0)
        
        return send_file(
            out_stream,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"cloudvault_{report_type}_report.pdf"
        )
        
    return abort(400)

# ==========================================================================
# NOTIFICATION LOGS
# ==========================================================================
@admin_bp.route("/notifications")
@login_required
@admin_required
def notifications():
    page = request.args.get('page', 1, type=int)
    
    # Query admin-targeted notifications (e.g. storage limits, failed logs, system alerts)
    # Since admin logs might be in a general list or flagged, let's query all system type notifications
    system_notifications = Notification.query.filter(
        Notification.notification_type.in_(['STORAGE_WARNING', 'SYSTEM_ALERT', 'EMAIL_FAILURE'])
    ).order_by(Notification.created_at.desc()).paginate(page=page, per_page=15)
    
    return render_template('admin/notifications.html', notifications=system_notifications)
