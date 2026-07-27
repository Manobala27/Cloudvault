import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'site.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # AWS Configuration
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '').strip() if os.environ.get('AWS_ACCESS_KEY_ID') else None
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '').strip() if os.environ.get('AWS_SECRET_ACCESS_KEY') else None
    AWS_REGION = os.environ.get('AWS_REGION', '').strip() if os.environ.get('AWS_REGION') else None
    S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', '').strip() if os.environ.get('S3_BUCKET_NAME') else None
    # Email transport configuration
    EMAIL_PROVIDER = os.environ.get('EMAIL_PROVIDER', 'smtp')  # 'smtp' or 'ses'

    # Flask-Mail configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() in ['true', 'on', '1']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'noreply@cloudvault.com'
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or 'admin@cloudvault.com'
