import re
from datetime import datetime, timezone
from flask import Blueprint, render_template, url_for, flash, redirect, request, current_app
from itsdangerous import URLSafeTimedSerializer
from flask_login import login_user, current_user, logout_user, login_required
from app import db, bcrypt, limiter
from app.forms import RegistrationForm, LoginForm
from app.models import User, ActivityLog
from app.services.email_service import email_service

auth = Blueprint('auth', __name__)

def parse_user_agent(ua_string):
    """Helper to extract browser, OS, and device type from User-Agent string."""
    if not ua_string:
        return {"os": "Unknown OS", "browser": "Unknown Browser", "device": "Unknown Device"}
    
    # Browser detection
    browser = "Unknown Browser"
    if "Firefox" in ua_string and "Seamonkey" not in ua_string:
        browser = "Firefox"
    elif "Chrome" in ua_string and "Safari" in ua_string and "Edge" not in ua_string and "Edg" not in ua_string:
        browser = "Chrome"
    elif "Safari" in ua_string and "Chrome" not in ua_string:
        browser = "Safari"
    elif "MSIE" in ua_string or "Trident" in ua_string:
        browser = "Internet Explorer"
    elif "Edge" in ua_string or "Edg" in ua_string:
        browser = "Microsoft Edge"
        
    # OS detection
    os_name = "Unknown OS"
    if "Windows" in ua_string:
        os_name = "Windows"
    elif "Macintosh" in ua_string or "Mac OS X" in ua_string:
        os_name = "macOS"
    elif "Linux" in ua_string:
        os_name = "Linux"
    elif "Android" in ua_string:
        os_name = "Android"
    elif "iPhone" in ua_string or "iPad" in ua_string:
        os_name = "iOS"
        
    # Device detection
    device = "Desktop"
    if "Mobi" in ua_string or "Android" in ua_string or "iPhone" in ua_string:
        device = "Mobile"
    elif "iPad" in ua_string or "Tablet" in ua_string:
        device = "Tablet"
        
    return {"os": os_name, "browser": browser, "device": device}

def handle_login_success(user, response, req):
    """Resets failed login attempts and triggers a login alert email if device is unrecognized."""
    user.failed_login_attempts = 0
    db.session.commit()
    
    ua_string = req.headers.get('User-Agent', '')
    parsed_ua = parse_user_agent(ua_string)
    ip_addr = req.headers.get('X-Forwarded-For', req.remote_addr)
    cookie_key = f"known_device_{user.id}"
    
    if not req.cookies.get(cookie_key):
        metadata = {
            "time": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
            "browser": parsed_ua["browser"],
            "os": parsed_ua["os"],
            "device": parsed_ua["device"],
            "ip": ip_addr,
            "location": "Unknown"
        }
        email_service.send_login_alert(user, metadata)
        response.set_cookie(cookie_key, "true", max_age=31536000)
    return response

@auth.route("/register", methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    from app.services.settings_service import settings_service
    if not settings_service.get('registration_enabled'):
        flash("New user registrations are currently disabled by the administrator.", "warning")
        return redirect(url_for('auth.login'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password, email_verified=False)
        db.session.add(user)
        db.session.commit()
        
        # Log Registration
        log = ActivityLog(user_id=user.id, action='REGISTER', ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        
        # Generate token & trigger emails
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = serializer.dumps(user.email, salt='email-verify-salt')
        
        email_service.send_welcome_email(user)
        email_service.send_verification_email(user, token)
        email_service.send_admin_notification(
            "New User Registration",
            f"User: {user.username}\nEmail: {user.email}\nRegistered at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        
        flash('Your account has been created! A verification link has been sent to your email. Please verify to access all features.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html', title='Register', form=form)

@auth.route("/login", methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                if not user.is_active:
                    flash("Your account has been disabled by an administrator.", "danger")
                    return redirect(url_for('auth.login'))
                    
                # Check if 2FA is enabled and if the device is trusted
                device_trusted = False
                device_token = request.cookies.get('trusted_device_token')
                if user.trusted_device_expiry and user.trusted_device_expiry.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
                    if user.trusted_device_token and device_token == user.trusted_device_token:
                        device_trusted = True
                    
                print(f"DEBUG LOGIN: user={user.email}, 2fa_enabled={user.two_factor_enabled}, trusted={device_trusted}")
                    
                if user.two_factor_enabled and not device_trusted:
                    from flask import session
                    session['2fa_user_id'] = user.id
                    session['2fa_remember'] = form.remember.data
                    session['2fa_next_page'] = request.args.get('next')
                    return redirect(url_for('security.verify_2fa'))
                    
                login_user(user, remember=form.remember.data)
                
                # Log Login
                log = ActivityLog(user_id=user.id, action='LOGIN', ip_address=request.remote_addr)
                if user.is_admin:
                    log = ActivityLog(user_id=user.id, action='ADMIN_LOGIN', ip_address=request.remote_addr)
                db.session.add(log)
                db.session.commit()
                
                next_page = request.args.get('next')
                flash('Login successful!', 'success')
                
                # Render redirect with handle_login_success device check
                response = redirect(next_page) if next_page else redirect(url_for('files.dashboard'))
                return handle_login_success(user, response, request)
            else:
                user.failed_login_attempts += 1
                db.session.commit()
                
                if user.failed_login_attempts >= 5:
                    metadata = {
                        "attempts": user.failed_login_attempts,
                        "time": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
                        "ip": request.remote_addr
                    }
                    email_service.send_failed_login_alert(user, metadata)
                    email_service.send_admin_notification(
                        "Multiple Failed Logins",
                        f"Multiple failed login attempts on user account: {user.email}\nTotal failed attempts: {user.failed_login_attempts}\nIP: {request.remote_addr}"
                    )
                flash('Login Unsuccessful. Please check email and password', 'danger')
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)

@auth.route("/logout")
def logout():
    if current_user.is_authenticated:
        # Log Logout before logging the user out
        log = ActivityLog(user_id=current_user.id, action='LOGOUT', ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        
    logout_user()
    return redirect(url_for('main.index'))

@auth.route("/forgot_password", methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        user = User.query.filter_by(email=email).first()
        if user:
            serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            token = serializer.dumps(user.email, salt='password-reset-salt')
            email_service.send_password_reset_email(user, token)
        flash('If an account exists with that email, a password reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/forgot_password.html')

@auth.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=1800) # 30 mins
    except:
        flash('That is an invalid or expired token. Please try again.', 'danger')
        return redirect(url_for('auth.forgot_password'))
        
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('User does not exist.', 'danger')
        return redirect(url_for('auth.forgot_password'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        pattern = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')
        if not password or not pattern.match(password):
            flash("Password must be at least 8 characters long and include one uppercase letter, one lowercase letter, one number, and one special character (@$!%*?&).", "danger")
            return render_template('auth/reset_password.html')
            
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('auth/reset_password.html')
            
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user.password = hashed_password
        user.failed_login_attempts = 0
        db.session.commit()
        
        ua_string = request.headers.get('User-Agent', '')
        parsed_ua = parse_user_agent(ua_string)
        ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
        
        metadata = {
            "time": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
            "browser": parsed_ua["browser"],
            "os": parsed_ua["os"],
            "device": parsed_ua["device"],
            "ip": ip_addr,
            "location": "Unknown"
        }
        email_service.send_password_changed_email(user, metadata)
        
        flash('Your password has been successfully reset! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html')
