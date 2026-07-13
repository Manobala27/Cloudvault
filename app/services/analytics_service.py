from datetime import datetime, timedelta, timezone
from sqlalchemy import func, desc, or_
from app import db
from app.models import User, File, Folder, Share, ActivityLog, FileVersion
import mimetypes

class AnalyticsService:
    @staticmethod
    def get_user_analytics(user_id, days=None):
        query_filter = [File.user_id == user_id, File.is_deleted == False]
        if days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            query_filter.append(File.upload_date >= cutoff)
            
        files = File.query.filter(*query_filter).all()
        
        total_files = len(files)
        total_size = sum(f.file_size for f in files if f.file_size)
        total_folders = Folder.query.filter_by(user_id=user_id, is_deleted=False).count()
        
        # Trash stats
        trash_files = File.query.filter_by(user_id=user_id, is_deleted=True).all()
        trash_count = len(trash_files)
        trash_size = sum(f.file_size for f in trash_files if f.file_size)
        
        # Favorites, Shares, Versions
        total_favorites = sum(1 for f in files if getattr(f, 'is_favorite', False))
        total_favorites += Folder.query.filter_by(user_id=user_id, is_deleted=False, is_favorite=True).count()
        total_shares = Share.query.join(File).filter(File.user_id == user_id).count()
        
        # We need total versions for this user's files
        file_ids = [f.id for f in files]
        total_versions = 0
        if file_ids:
            total_versions = FileVersion.query.filter(FileVersion.file_id.in_(file_ids)).count()

        # File sizes
        largest_file = max(files, key=lambda f: f.file_size or 0) if files else None
        smallest_file = min([f for f in files if f.file_size], key=lambda f: f.file_size) if [f for f in files if f.file_size] else None
        avg_size = total_size / total_files if total_files > 0 else 0

        # Storage capacity (Assumed 15GB standard, could be pulled from user model if exists)
        # Let's assume a hard limit of 15GB (15 * 1024**3)
        storage_quota = 15 * 1024 * 1024 * 1024 
        storage_percent = (total_size / storage_quota) * 100 if storage_quota > 0 else 0
        
        # File type grouping
        types = {'Images': 0, 'Videos': 0, 'Audio': 0, 'Documents': 0, 'Archives': 0, 'Code': 0, 'Others': 0}
        type_sizes = {k: 0 for k in types.keys()}
        
        for f in files:
            mime, _ = mimetypes.guess_type(f.original_filename)
            category = 'Others'
            if mime:
                if mime.startswith('image/'): category = 'Images'
                elif mime.startswith('video/'): category = 'Videos'
                elif mime.startswith('audio/'): category = 'Audio'
                elif mime in ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']: category = 'Documents'
                elif mime in ['application/zip', 'application/x-tar', 'application/x-rar-compressed']: category = 'Archives'
                elif mime.startswith('text/') or mime in ['application/json', 'application/javascript']: category = 'Code'
            
            types[category] += 1
            type_sizes[category] += (f.file_size or 0)
            
        # Recent Uploads
        recent_uploads = File.query.filter_by(user_id=user_id, is_deleted=False).order_by(desc(File.upload_date)).limit(5).all()

        # Trend Data (Last 30 days upload count)
        trend_dates = []
        trend_counts = []
        trend_sizes = []
        now = datetime.now(timezone.utc)
        for i in range(29, -1, -1):
            date = (now - timedelta(days=i)).date()
            trend_dates.append(date.strftime("%Y-%m-%d"))
            
            day_files = [f for f in files if f.upload_date and f.upload_date.date() == date]
            trend_counts.append(len(day_files))
            trend_sizes.append(sum(f.file_size for f in day_files if f.file_size))

        return {
            'storage_used': total_size,
            'storage_quota': storage_quota,
            'storage_percent': min(storage_percent, 100),
            'total_files': total_files,
            'total_folders': total_folders,
            'total_favorites': total_favorites,
            'total_shares': total_shares,
            'total_versions': total_versions,
            'trash_count': trash_count,
            'trash_size': trash_size,
            'largest_file': {'name': largest_file.original_filename, 'size': largest_file.file_size} if largest_file else None,
            'smallest_file': {'name': smallest_file.original_filename, 'size': smallest_file.file_size} if smallest_file else None,
            'avg_size': avg_size,
            'type_counts': types,
            'type_sizes': type_sizes,
            'recent_uploads': [{'name': f.original_filename, 'size': f.file_size, 'date': f.upload_date.isoformat()} for f in recent_uploads],
            'trend': {
                'dates': trend_dates,
                'counts': trend_counts,
                'sizes': trend_sizes
            }
        }
        
    @staticmethod
    def get_admin_analytics():
        users = User.query.all()
        total_users = len(users)
        
        all_files = File.query.filter_by(is_deleted=False).all()
        total_files = len(all_files)
        total_storage = sum(f.file_size for f in all_files if f.file_size)
        total_shares = Share.query.count()
        
        # 2FA Stats
        two_factor_enabled_count = sum(1 for u in users if u.two_factor_enabled)
        two_factor_disabled_count = total_users - two_factor_enabled_count
        
        # API Stats
        from app.models import APIKey
        all_keys = APIKey.query.all()
        total_api_keys = len(all_keys)
        active_api_keys = sum(1 for k in all_keys if k.is_active)
        revoked_api_keys = total_api_keys - active_api_keys
        
        avg_user_storage = total_storage / total_users if total_users > 0 else 0
        
        # User storage list to find largest
        user_storages = {}
        for f in all_files:
            user_storages[f.user_id] = user_storages.get(f.user_id, 0) + (f.file_size or 0)
            
        largest_user_id = max(user_storages, key=user_storages.get) if user_storages else None
        largest_user = User.query.get(largest_user_id) if largest_user_id else None
        
        newest_users = User.query.order_by(desc(User.created_at)).limit(5).all() if hasattr(User, 'created_at') else User.query.order_by(desc(User.id)).limit(5).all()
        
        # Activity trend (last 7 days total logs)
        trend_dates = []
        trend_activity = []
        now = datetime.now(timezone.utc)
        for i in range(6, -1, -1):
            date = (now - timedelta(days=i)).date()
            trend_dates.append(date.strftime("%Y-%m-%d"))
            
            # This could be expensive on large DBs, using SQL directly is better
            # but for our scale, we can query it
            start = datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
            end = start + timedelta(days=1)
            count = ActivityLog.query.filter(ActivityLog.created_at >= start, ActivityLog.created_at < end).count()
            trend_activity.append(count)

        return {
            'total_users': total_users,
            'total_files': total_files,
            'total_shares': total_shares,
            'total_storage': total_storage,
            'avg_user_storage': avg_user_storage,
            'two_factor_enabled': two_factor_enabled_count,
            'two_factor_disabled': two_factor_disabled_count,
            'api_stats': {
                'total_keys': total_api_keys,
                'active_keys': active_api_keys,
                'revoked_keys': revoked_api_keys
            },
            'largest_user': {
                'username': largest_user.username if largest_user else 'None',
                'storage': user_storages.get(largest_user_id, 0) if largest_user_id else 0
            },
            'newest_users': [{'username': u.username, 'email': u.email} for u in newest_users],
            'trend': {
                'dates': trend_dates,
                'activity': trend_activity
            }
        }

analytics_service = AnalyticsService()
