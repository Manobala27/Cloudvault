from flask import Blueprint, render_template, url_for, flash, redirect, request, abort
from app import db, bcrypt
from app.models import User, File, Folder, Share, ActivityLog
from app.s3_service import s3_service
from flask_login import current_user, login_required
from functools import wraps

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    disabled_users = User.query.filter_by(is_active=False).count()
    
    total_files = File.query.filter_by(is_deleted=False).count()
    total_shared_files = Share.query.filter_by(is_active=True).count()
    
    # Calculate total storage used
    from app.models import FileVersion
    all_versions = FileVersion.query.all()
    total_storage_used = sum(v.file_size for v in all_versions)
    
    total_activity_logs = ActivityLog.query.count()
    
    return render_template('admin/dashboard.html',
                           total_users=total_users,
                           active_users=active_users,
                           disabled_users=disabled_users,
                           total_files=total_files,
                           total_shared_files=total_shared_files,
                           total_storage_used=total_storage_used,
                           total_activity_logs=total_activity_logs)

@admin_bp.route("/users")
@login_required
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    
    query = User.query
    if search_query:
        query = query.filter((User.username.ilike(f"%{search_query}%")) | (User.email.ilike(f"%{search_query}%")))
        
    users_paginated = query.order_by(User.id.asc()).paginate(page=page, per_page=15)
    
    # Precompute total storage per user manually to support versioning correctly
    for u in users_paginated.items:
        u_versions = FileVersion.query.filter_by(uploaded_by=u.id).all()
        u._total_storage = sum(v.file_size for v in u_versions)
    
    return render_template('admin/users.html', users=users_paginated, search_query=search_query)

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
    action = 'ENABLE_USER' if user.is_active else 'DISABLE_USER'
    
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
    action = 'PROMOTE_ADMIN' if user.is_admin else 'REMOVE_ADMIN'
    
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
            
    # Hard Delete: Files in S3, DB Records (Files, Folders, Shares, Logs, User)
    files = File.query.filter_by(user_id=user.id).all()
    for f in files:
        for v in f.versions:
            try:
                s3_service.delete_file(v.s3_key)
            except Exception:
                pass
        try:
            s3_service.delete_file(f.filename)
        except Exception:
            pass
    
    # DB cascade deletion handles the rest if configured, but let's be explicit
    file_ids = [f.id for f in files]
    if file_ids:
        Share.query.filter(Share.file_id.in_(file_ids)).delete(synchronize_session=False)
    ActivityLog.query.filter_by(user_id=user.id).delete()
    File.query.filter_by(user_id=user.id).delete()
    Folder.query.filter_by(user_id=user.id).delete()
    
    username = user.username
    db.session.delete(user)
    
    log = ActivityLog(user_id=current_user.id, action='DELETE_USER', file_name=username, ip_address=request.remote_addr)
    db.session.add(log)
    
    db.session.commit()
    
    flash(f"User {username} and all associated data have been permanently deleted.", "success")
    return redirect(url_for('admin.users'))
