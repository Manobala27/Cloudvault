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

