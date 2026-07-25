from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, make_response, current_app
from flask_login import login_required, current_user
from itsdangerous import URLSafeTimedSerializer
from app.models import ActivityLog, User
from app.services.two_factor_service import two_factor_service
from app.services.notification_service import notification_service
from app.services.email_service import email_service
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
            
            # Update last_2fa_used
            from datetime import datetime, timedelta, timezone
            user.last_2fa_used = datetime.now(timezone.utc)
            db.session.commit()
            
            response = make_response(redirect(next_page) if next_page else redirect(url_for('main.index')))
            
            # Trust device if requested
            if trust_device:
                import secrets
                token = secrets.token_hex(32)
                user.trusted_device_token = token
                user.trusted_device_expiry = datetime.now(timezone.utc) + timedelta(days=30)
                db.session.commit()
                
                # Set cookie
                response.set_cookie('trusted_device_token', token, max_age=30*24*60*60, httponly=True, secure=request.is_secure)
                
                log = ActivityLog(user_id=user.id, action='TRUSTED_DEVICE_CREATED', ip_address=request.remote_addr)
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
            log = ActivityLog(user_id=user.id, action='OTP_SUCCESS', ip_address=request.remote_addr)
            db.session.add(log)
            db.session.commit()
            
            # Clear 2FA session data
            session.pop('2fa_user_id', None)
            session.pop('2fa_remember', None)
            session.pop('2fa_next_page', None)
            
            from app.routes.auth import handle_login_success
            flash('Login successful!', 'success')
            return handle_login_success(user, response, request)
        else:
            # Log failed attempt
            log = ActivityLog(user_id=user.id, action='OTP_FAILED', ip_address=request.remote_addr)
            db.session.add(log)
            db.session.commit()
            
            notification_service.create_notification(
                user_id=user.id,
                title="Failed OTP Attempt",
                message="A failed 2FA verification attempt occurred.",
                notification_type="SECURITY_WARNING",
                icon="bi-exclamation-triangle"
            )
            
            flash('Invalid verification code.', 'danger')
            
    return render_template('auth/verify_2fa.html', title='Two-Factor Verification')

@security_bp.route('/2fa/trust', methods=['POST'])
@login_required
def remove_trust():
    action = request.get_json().get('action')
    if action == 'remove':
        current_user.trusted_device_token = None
        current_user.trusted_device_expiry = None
        
        log = ActivityLog(user_id=current_user.id, action='TRUSTED_DEVICE_REMOVED', ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        
        notification_service.create_notification(
            user_id=current_user.id,
            title="Trusted Device Removed",
            message="This device is no longer trusted.",
            notification_type="SECURITY",
            icon="bi-laptop"
        )
        
        res = make_response(jsonify({'success': True}))
        res.delete_cookie('trusted_device_token')
        return res
    return jsonify({'success': False})

@security_bp.route('/unverified', methods=['GET'])
@login_required
def unverified():
    if current_user.email_verified:
        return redirect(url_for('files.dashboard'))
    return render_template('auth/unverified.html')

@security_bp.route('/verify-email/<token>', methods=['GET'])
def verify_email(token):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        token_email = serializer.loads(token, salt='email-verify-salt', max_age=86400) # 24 hours
    except:
        flash("The verification link is invalid or has expired.", "danger")
        return redirect(url_for('auth.login'))
        
    user = User.query.filter_by(pending_new_email=token_email).first()
    if user:
        old_email = user.email
        user.email = token_email
        user.pending_new_email = None
        user.email_verified = True
        db.session.commit()
        
        subject_old = "CloudVault: Email Changed Successfully"
        html_old = f"<p>Hello {user.username},</p><p>This email confirms that your CloudVault account email address has been successfully changed from <strong>{old_email}</strong> to <strong>{token_email}</strong>.</p>"
        email_service._send_email(old_email, subject_old, html_old, "EMAIL_CHANGED_OLD")
        
        subject_new = "CloudVault: Email Verified Successfully"
        html_new = f"<p>Hello {user.username},</p><p>Your email address <strong>{token_email}</strong> has been verified successfully. Your account is now fully active.</p>"
        email_service._send_email(token_email, subject_new, html_new, "EMAIL_CHANGED_NEW")
        
        flash("Your email address has been successfully verified and updated!", "success")
        if current_user.is_authenticated:
            return redirect(url_for('files.dashboard'))
        return redirect(url_for('auth.login'))
        
    user = User.query.filter_by(email=token_email).first()
    if user:
        user.email_verified = True
        db.session.commit()
        
        flash("Your email address has been successfully verified!", "success")
        if current_user.is_authenticated:
            return redirect(url_for('files.dashboard'))
        return redirect(url_for('auth.login'))
        
    flash("User account not found.", "danger")
    return redirect(url_for('auth.login'))

@security_bp.route('/resend-verification', methods=['POST'])
@login_required
def resend_verification():
    if current_user.email_verified:
        flash("Your email is already verified.", "info")
        return redirect(url_for('files.dashboard'))
        
    target_email = current_user.pending_new_email if current_user.pending_new_email else current_user.email
    
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    token = serializer.dumps(target_email, salt='email-verify-salt')
    
    # Render verify email with the target email
    class TempUser:
        def __init__(self, username, email):
            self.username = username
            self.email = email
            
    user_for_render = TempUser(current_user.username, target_email)
    email_service.send_verification_email(user_for_render, token)
    
    flash(f"A new verification link has been sent to '{target_email}'.", "success")
    return redirect(url_for('security.unverified'))

@security_bp.route('/change_email', methods=['POST'])
@login_required
def change_email():
    new_email = request.form.get('new_email', '').strip()
    password = request.form.get('password')
    
    if not new_email or not password:
        flash("All fields are required.", "danger")
        return redirect(url_for('security.settings'))
        
    if not bcrypt.check_password_hash(current_user.password, password):
        flash("Incorrect password. Email change cancelled.", "danger")
        return redirect(url_for('security.settings'))
        
    existing_user = User.query.filter_by(email=new_email).first()
    if existing_user:
        flash("That email address is already registered.", "danger")
        return redirect(url_for('security.settings'))
        
    current_user.pending_new_email = new_email
    db.session.commit()
    
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    token = serializer.dumps(new_email, salt='email-verify-salt')
    
    class TempUser:
        def __init__(self, username, email):
            self.username = username
            self.email = email
            
    user_for_render = TempUser(current_user.username, new_email)
    email_service.send_verification_email(user_for_render, token)
    
    # Notify old email
    subject = "CloudVault: Request to Change Your Email Address"
    html_content = f"<p>Hello {current_user.username},</p><p>We received a request to change the email address of your CloudVault account to <strong>{new_email}</strong>.</p><p>A verification link has been sent to the new email address. Your current email remains active until verified.</p><p>If you did not request this, please secure your account immediately.</p>"
    email_service._send_email(current_user.email, subject, html_content, "EMAIL_CHANGE_REQUESTED")
    
    flash(f"Verification link sent to '{new_email}'. Your email will update once verified.", "success")
    return redirect(url_for('security.settings'))

@security_bp.route('/update_preferences', methods=['POST'])
@login_required
def update_preferences():
    current_user.pref_welcome_email = 'pref_welcome_email' in request.form
    current_user.pref_share_emails = 'pref_share_emails' in request.form
    current_user.pref_login_alerts = 'pref_login_alerts' in request.form
    current_user.pref_storage_alerts = 'pref_storage_alerts' in request.form
    current_user.pref_security_alerts = 'pref_security_alerts' in request.form
    current_user.pref_product_updates = 'pref_product_updates' in request.form
    
    db.session.commit()
    flash("Your notification preferences have been updated.", "success")
    return redirect(url_for('security.settings'))

