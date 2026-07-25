from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from app.s3_service import s3_service
from app.services.email_service import email_service

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html', title='Home')

@main.route('/test-s3')
def test_s3():
    success, message = s3_service.verify_connection()
    return jsonify({
        "status": "success" if success else "error",
        "message": message
    })

@main.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        
        if not name or not email or not subject or not message:
            flash("All fields are required.", "danger")
            return redirect(url_for('main.contact'))
            
        success = email_service.send_contact_email(name, email, subject, message)
        if success:
            flash("Your support inquiry has been sent successfully. We'll contact you soon!", "success")
        else:
            flash("Failed to send support request. Please try again later or contact us directly.", "danger")
            
        return redirect(url_for('main.contact'))
        
    return render_template('contact.html')
