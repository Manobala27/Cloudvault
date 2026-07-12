from flask import Blueprint, render_template, jsonify
from app.s3_service import s3_service

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


