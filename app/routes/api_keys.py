from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app.services.api_key_service import api_key_service
from app.services.notification_service import notification_service
from app.models import ActivityLog
from app import db
from datetime import datetime, timedelta, timezone

api_keys_bp = Blueprint('api_keys', __name__, url_prefix='/settings/api-keys')

@api_keys_bp.route('/')
@login_required
def index():
    return render_template('api_keys.html', title='API Keys')

@api_keys_bp.route('/docs')
@login_required
def docs():
    return render_template('api_docs.html', title='API Documentation')

@api_keys_bp.route('/generate', methods=['POST'])
@login_required
def generate():
    data = request.get_json()
    name = data.get('name')
    expiry_days = data.get('expiry_days')
    
    if not name:
        return jsonify({'success': False, 'message': 'API key name is required.'}), 400
        
    expires_at = None
    if expiry_days and expiry_days != 'never':
        expires_at = datetime.now(timezone.utc) + timedelta(days=int(expiry_days))
        
    raw_key, api_key = api_key_service.generate_api_key(current_user.id, name, expires_at)
    
    log = ActivityLog(user_id=current_user.id, action='API_KEY_CREATED', ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    
    notification_service.create_notification(
        user_id=current_user.id,
        title="API Key Created",
        message=f"API key '{name}' has been created.",
        notification_type="SECURITY",
        icon="bi-key-fill"
    )
    
    return jsonify({
        'success': True,
        'raw_key': raw_key,
        'key_id': api_key.id
    })

@api_keys_bp.route('/revoke/<int:key_id>', methods=['POST'])
@login_required
def revoke(key_id):
    if api_key_service.revoke_key(key_id, current_user.id):
        log = ActivityLog(user_id=current_user.id, action='API_KEY_REVOKED', ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        
        notification_service.create_notification(
            user_id=current_user.id,
            title="API Key Revoked",
            message="An API key has been securely revoked.",
            notification_type="SECURITY",
            icon="bi-shield-slash"
        )
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'API key not found.'}), 404

@api_keys_bp.route('/delete/<int:key_id>', methods=['POST'])
@login_required
def delete(key_id):
    if api_key_service.delete_key(key_id, current_user.id):
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'API key not found.'}), 404
