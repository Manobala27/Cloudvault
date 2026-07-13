from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file, jsonify
from flask_login import login_required, current_user
from app.services.backup_service import backup_service
from app.services.notification_service import notification_service
from app.models import Backup, ActivityLog
from app import db
import os

backups_bp = Blueprint('backups', __name__, url_prefix='/backups')

@backups_bp.route('/', methods=['GET'])
@login_required
def index():
    user_backups = Backup.query.filter_by(user_id=current_user.id).order_by(Backup.created_at.desc()).all()
    return render_template('backups.html', title='Backup & Restore', backups=user_backups)

@backups_bp.route('/create', methods=['POST'])
@login_required
def create():
    name = request.form.get('backup_name')
    b_type = request.form.get('backup_type', 'Full')
    
    if not name:
        flash('Backup name is required.', 'danger')
        return redirect(url_for('backups.index'))
        
    success, result = backup_service.generate_backup(current_user.id, name, b_type)
    if success:
        notification_service.create_notification(
            user_id=current_user.id,
            title="Backup Completed",
            message=f"Backup '{name}' has been created successfully.",
            notification_type="SYSTEM",
            icon="bi-cloud-check"
        )
        flash('Backup created successfully.', 'success')
    else:
        notification_service.create_notification(
            user_id=current_user.id,
            title="Backup Failed",
            message=f"Backup '{name}' failed to generate.",
            notification_type="SYSTEM",
            icon="bi-x-circle"
        )
        flash(f'Backup creation failed: {result}', 'danger')
        
    return redirect(url_for('backups.index'))

@backups_bp.route('/restore/<int:id>', methods=['POST'])
@login_required
def restore(id):
    options = request.form.getlist('restore_options')
    if not options:
        flash('Please select at least one option to restore.', 'warning')
        return redirect(url_for('backups.index'))
        
    success, msg = backup_service.restore_backup(id, current_user.id, options)
    if success:
        notification_service.create_notification(
            user_id=current_user.id,
            title="Restore Completed",
            message="Selected backup settings have been restored.",
            notification_type="SYSTEM",
            icon="bi-arrow-counterclockwise"
        )
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
        
    return redirect(url_for('backups.index'))

@backups_bp.route('/download/<int:id>', methods=['GET'])
@login_required
def download(id):
    path = backup_service.get_backup_path(id, current_user.id)
    if path and os.path.exists(path):
        log = ActivityLog(user_id=current_user.id, action='BACKUP_DOWNLOADED', file_name=f"Downloaded backup ID {id}")
        db.session.add(log)
        db.session.commit()
        return send_file(path, as_attachment=True, download_name=os.path.basename(path))
    else:
        flash('Backup file not found on disk.', 'danger')
        return redirect(url_for('backups.index'))

@backups_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    if backup_service.delete_backup(id, current_user.id):
        flash('Backup deleted.', 'success')
    else:
        flash('Failed to delete backup.', 'danger')
    return redirect(url_for('backups.index'))
