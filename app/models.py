from datetime import datetime, timezone
from app import db, login_manager
from flask_login import UserMixin

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    password = db.Column(db.String(60), nullable=False)
    date_registered = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # 2FA (Module 21)
    two_factor_enabled = db.Column(db.Boolean, default=False, nullable=False)
    two_factor_secret = db.Column(db.String(255), nullable=True) # Encrypted String
    backup_codes = db.Column(db.Text, nullable=True) # Encrypted JSON or text
    trusted_device_token = db.Column(db.String(255), nullable=True)
    trusted_device_expiry = db.Column(db.DateTime, nullable=True)
    last_2fa_used = db.Column(db.DateTime, nullable=True)
    
    files = db.relationship('File', backref='owner', lazy=True)
    folders = db.relationship('Folder', backref='owner', lazy=True)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.image_file}')"

# Many-to-Many Association Tables for Tags (Module 16)
file_tag = db.Table('file_tag',
    db.Column('file_id', db.Integer, db.ForeignKey('file.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

folder_tag = db.Table('folder_tag',
    db.Column('folder_id', db.Integer, db.ForeignKey('folder.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    color_hex = db.Column(db.String(7), nullable=False, default='#0d6efd')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('name', 'user_id', name='_user_tag_uc'),)

    def __repr__(self):
        return f"Tag('{self.name}', '{self.color_hex}')"

class Folder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)
    
    # Soft delete fields
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    # Favorites (Module 15)
    is_favorite = db.Column(db.Boolean, default=False, nullable=False)
    favorited_at = db.Column(db.DateTime, nullable=True)
    
    # Self-referential relationship for subfolders
    subfolders = db.relationship('Folder', backref=db.backref('parent', remote_side=[id]), lazy=True, cascade="all, delete-orphan")
    
    # Files in this folder
    files = db.relationship('File', backref='folder', lazy=True, cascade="all, delete-orphan")
    
    # Tags (Module 16)
    tags = db.relationship('Tag', secondary=folder_tag, lazy='subquery', backref=db.backref('folders', lazy=True))

    def __repr__(self):
        return f"Folder('{self.name}', '{self.created_at}')"

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False) # S3 Key / Unique name
    original_filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    file_size = db.Column(db.Integer, nullable=False) # Size in bytes
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)
    
    # Soft delete fields
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    # Sharing functionality (Legacy / Deprecated for new shares)
    share_token = db.Column(db.String(36), unique=True, nullable=True) # UUID length is 36
    share_expires_at = db.Column(db.DateTime, nullable=True)
    
    # Advanced Sharing (Module 12)
    shares = db.relationship('Share', backref='file', lazy=True, cascade="all, delete-orphan")

    # File Versioning (Module 14)
    versions = db.relationship('FileVersion', backref='file', lazy=True, cascade="all, delete-orphan")

    # Favorites (Module 15)
    is_favorite = db.Column(db.Boolean, default=False, nullable=False)
    favorited_at = db.Column(db.DateTime, nullable=True)

    # Tags (Module 16)
    tags = db.relationship('Tag', secondary=file_tag, lazy='subquery', backref=db.backref('files', lazy=True))

    def __repr__(self):
        return f"File('{self.original_filename}', '{self.upload_date}')"

class FileVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('file.id'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    s3_key = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_current = db.Column(db.Boolean, default=False, nullable=False)

    uploader = db.relationship('User', foreign_keys=[uploaded_by])

    def __repr__(self):
        return f"FileVersion(V{self.version_number}, file_id={self.file_id}, current={self.is_current})"

class Share(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('file.id'), nullable=False)
    share_token = db.Column(db.String(36), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    download_limit = db.Column(db.Integer, nullable=True) # None = unlimited
    download_count = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"Share('{self.share_token}', active={self.is_active})"

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)
    file_name = db.Column(db.String(255), nullable=True)
    folder_name = db.Column(db.String(255), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('activities', lazy=True))

    def __repr__(self):
        return f"ActivityLog('{self.action}', '{self.created_at}')"

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)
    icon = db.Column(db.String(50), nullable=True, default='bi-bell')
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    action_url = db.Column(db.String(255), nullable=True)

    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f"Notification('{self.title}', '{self.notification_type}', read={self.is_read})"
