from flask import Blueprint, render_template, url_for, flash, redirect, request
from app import db, bcrypt, limiter
from app.forms import RegistrationForm, LoginForm
from app.models import User, ActivityLog
from flask_login import login_user, current_user, logout_user, login_required

auth = Blueprint('auth', __name__)

@auth.route("/register", methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        
        # Log Registration
        log = ActivityLog(user_id=user.id, action='REGISTER', ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        
        flash('Your account has been created! You are now able to log in', 'success')
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
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            if not user.is_active:
                flash("Your account has been disabled by an administrator.", "danger")
                return redirect(url_for('auth.login'))
                
            from datetime import datetime, timezone
            
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
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
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
