from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, make_response
from flask_login import login_required, current_user
from app.models import ActivityLog
from app.services.two_factor_service import two_factor_service
from app.services.notification_service import notification_service
from app import db
import io
import csv

security_bp = Blueprint('security', __name__, url_prefix='/security')

@security_bp.route('/', methods=['GET'])
@login_required
def settings():
    secret = None
    qr_code = None
    
    # If 2FA is not enabled, generate a temporary secret and QR for the setup process
    if not current_user.two_factor_enabled:
        secret = session.get('temp_2fa_secret')
        if not secret:
            secret = two_factor_service.generate_secret()
            session['temp_2fa_secret'] = secret
            
        uri = two_factor_service.get_totp_uri(current_user.email, secret)
        qr_code = two_factor_service.generate_qr_code(uri)
        
    return render_template('security.html', secret=secret, qr_code=qr_code)

@security_bp.route('/2fa/enable', methods=['POST'])
@login_required
def enable_2fa():
    if current_user.two_factor_enabled:
        return jsonify({'success': False, 'message': '2FA is already enabled'})
        
    data = request.get_json()
    token = data.get('token')
    secret = session.get('temp_2fa_secret')
    
    if not token or not secret:
        return jsonify({'success': False, 'message': 'Missing token or secret'})
        
    if two_factor_service.verify_totp(secret, token):
        current_user.two_factor_secret = secret
        current_user.two_factor_enabled = True
        
        # Generate initial recovery codes
        raw_codes = two_factor_service.generate_recovery_codes(current_user)
        
        # Clear temp secret
        session.pop('temp_2fa_secret', None)
        
        # Log and Notify
        log = ActivityLog(user_id=current_user.id, action='2FA_ENABLED', ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        
        notification_service.create_notification(
            user_id=current_user.id,
            title="Two-Factor Authentication Enabled",
            message="Your account is now protected with 2FA.",
            notification_type="SECURITY",
            icon="bi-shield-lock-fill"
        )
        
        return jsonify({'success': True, 'recovery_codes': raw_codes})
    
    return jsonify({'success': False, 'message': 'Invalid verification code'})

@security_bp.route('/2fa/disable', methods=['POST'])
@login_required
def disable_2fa():
    data = request.get_json()
    password = data.get('password')
    
    from app import bcrypt
    if not bcrypt.check_password_hash(current_user.password, password):
         return jsonify({'success': False, 'message': 'Incorrect password'})
         
    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    current_user.backup_codes = None
    
    # Log and Notify
    log = ActivityLog(user_id=current_user.id, action='2FA_DISABLED', ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    
    notification_service.create_notification(
        user_id=current_user.id,
        title="Two-Factor Authentication Disabled",
        message="Your account is no longer protected with 2FA. This is a security risk.",
        notification_type="SECURITY_WARNING",
        icon="bi-shield-slash-fill"
    )
    
    return jsonify({'success': True})

@security_bp.route('/2fa/regenerate', methods=['POST'])
@login_required
def regenerate_recovery_codes():
    if not current_user.two_factor_enabled:
        return jsonify({'success': False, 'message': '2FA is not enabled'})
        
    raw_codes = two_factor_service.generate_recovery_codes(current_user)
    
    log = ActivityLog(user_id=current_user.id, action='RECOVERY_CODES_REGENERATED', ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    
    notification_service.create_notification(
        user_id=current_user.id,
        title="Recovery Codes Regenerated",
        message="Your previous 2FA recovery codes have been invalidated.",
        notification_type="SECURITY",
        icon="bi-key-fill"
    )
    
    return jsonify({'success': True, 'recovery_codes': raw_codes})

@security_bp.route('/2fa/download-recovery', methods=['POST'])
@login_required
def download_recovery_codes():
    if not current_user.two_factor_enabled:
        flash("2FA is not enabled.", "danger")
        return redirect(url_for('security.settings'))
        
    codes_str = request.form.get('codes')
    if not codes_str:
        flash("No codes provided to download.", "danger")
        return redirect(url_for('security.settings'))
        
    output = io.StringIO()
    output.write("CloudVault 2FA Recovery Codes\n")
    output.write("Keep these safe. Each code can only be used once.\n\n")
    try:
        import ast
        codes = ast.literal_eval(codes_str)
        for code in codes:
            output.write(f"{code}\n")
    except:
        output.write(codes_str)
        
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=cloudvault_recovery_codes.txt"
    response.headers["Content-type"] = "text/plain"
    return response

@security_bp.route('/2fa/verify', methods=['GET', 'POST'])
def verify_2fa():
    from flask_login import login_user
    from app.models import User
    from app import limiter
    
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    user_id = session.get('2fa_user_id')
    if not user_id:
        flash("Session expired. Please log in again.", "danger")
        return redirect(url_for('auth.login'))
        
    user = User.query.get(user_id)
    if not user or not user.two_factor_enabled:
        session.pop('2fa_user_id', None)
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        token = request.form.get('token')
        action = request.form.get('action') # 'totp' or 'recovery'
        trust_device = request.form.get('trust_device')
        
        success = False
        
        if action == 'totp':
            success = two_factor_service.verify_totp(user.two_factor_secret, token)
        elif action == 'recovery':
            success = two_factor_service.verify_recovery_code(user, token)
            if success:
                # Log recovery code used
                log = ActivityLog(user_id=user.id, action='RECOVERY_CODE_USED', ip_address=request.remote_addr)
                db.session.add(log)
                db.session.commit()
                
        if success:
            remember = session.get('2fa_remember', False)
            next_page = session.get('2fa_next_page')
            
            # Trust device if requested
            if trust_device:
                from datetime import datetime, timedelta, timezone
                user.trusted_device_until = datetime.now(timezone.utc) + timedelta(days=30)
                db.session.commit()
                
                log = ActivityLog(user_id=user.id, action='TRUSTED_DEVICE_ADDED', ip_address=request.remote_addr)
                db.session.add(log)
                db.session.commit()
                
                notification_service.create_notification(
                    user_id=user.id,
                    title="Trusted Device Added",
                    message="This device has been trusted for 30 days.",
                    notification_type="SECURITY",
                    icon="bi-laptop"
                )
                
            login_user(user, remember=remember)
            
            # Log successful 2FA
            log = ActivityLog(user_id=user.id, action='2FA_SUCCESS', ip_address=request.remote_addr)
            db.session.add(log)
            db.session.commit()
            
            # Clear 2FA session data
            session.pop('2fa_user_id', None)
            session.pop('2fa_remember', None)
            session.pop('2fa_next_page', None)
            
            flash('Login successful!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            # Log failed attempt
            log = ActivityLog(user_id=user.id, action='2FA_FAILED', ip_address=request.remote_addr)
            db.session.add(log)
            db.session.commit()
            flash('Invalid verification code.', 'danger')
            
    return render_template('auth/verify_2fa.html', title='Two-Factor Verification')
