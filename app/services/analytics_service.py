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
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
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

        # Storage capacity configured in settings
        from app.services.settings_service import settings_service
        storage_quota = settings_service.get('storage_limit_gb') * 1024 * 1024 * 1024 
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
        now = datetime.now(timezone.utc).replace(tzinfo=None)
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
        
        # Backup Stats
        from app.models import Backup
        all_backups = Backup.query.all()
        total_backups = len(all_backups)
        backup_storage = sum(b.backup_size for b in all_backups)
        
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
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for i in range(6, -1, -1):
            date = (now - timedelta(days=i)).date()
            trend_dates.append(date.strftime("%Y-%m-%d"))
            start = datetime(date.year, date.month, date.day)
            end = start + timedelta(days=1)
            count = ActivityLog.query.filter(ActivityLog.created_at >= start, ActivityLog.created_at < end).count()
            trend_activity.append(count)

        # Extended admin analytics for Phase 3 charts
        # 1. Daily Registrations (last 30 days)
        reg_dates = []
        reg_counts = []
        for i in range(29, -1, -1):
            date = (now - timedelta(days=i)).date()
            reg_dates.append(date.strftime("%Y-%m-%d"))
            start = datetime(date.year, date.month, date.day)
            end = start + timedelta(days=1)
            count = User.query.filter(User.date_registered >= start, User.date_registered < end).count()
            reg_counts.append(count)

        # 2. Daily Uploads & Sizes (last 30 days)
        upload_dates = []
        upload_counts = []
        upload_sizes = []
        for i in range(29, -1, -1):
            date = (now - timedelta(days=i)).date()
            upload_dates.append(date.strftime("%Y-%m-%d"))
            start = datetime(date.year, date.month, date.day)
            end = start + timedelta(days=1)
            day_files_query = File.query.filter(File.upload_date >= start, File.upload_date < end, File.is_deleted == False).all()
            upload_counts.append(len(day_files_query))
            upload_sizes.append(sum(f.file_size for f in day_files_query if f.file_size))

        # 3. Storage Growth cumulative (last 30 days)
        growth_sizes = []
        cutoff_date = now - timedelta(days=30)
        base_storage = sum(f.file_size for f in all_files if f.upload_date and f.upload_date < cutoff_date and f.file_size)
        running = base_storage
        for i in range(29, -1, -1):
            date = (now - timedelta(days=i)).date()
            start = datetime(date.year, date.month, date.day)
            end = start + timedelta(days=1)
            day_files_query = File.query.filter(File.upload_date >= start, File.upload_date < end, File.is_deleted == False).all()
            running += sum(f.file_size for f in day_files_query if f.file_size)
            growth_sizes.append(running)

        # 4. File Type Distribution (across all files)
        types = {'Images': 0, 'Videos': 0, 'Audio': 0, 'Documents': 0, 'Archives': 0, 'Code': 0, 'Others': 0}
        type_sizes = {k: 0 for k in types.keys()}
        for f in all_files:
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

        # 5. Top 10 Storage Consumers
        sorted_consumers = sorted(user_storages.items(), key=lambda x: x[1], reverse=True)[:10]
        top_consumers = []
        for uid, size in sorted_consumers:
            u = User.query.get(uid)
            if u:
                top_consumers.append({
                    'username': u.username,
                    'email': u.email,
                    'storage_used': size
                })

        # 6. User Activity Distribution (grouped by log actions)
        activity_distribution = {}
        activity_counts = db.session.query(
            ActivityLog.action, func.count(ActivityLog.id)
        ).group_by(ActivityLog.action).all()
        for action, count in activity_counts:
            activity_distribution[action] = count

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
            'backup_stats': {
                'total_backups': total_backups,
                'storage': backup_storage
            },
            'largest_user': {
                'username': largest_user.username if largest_user else 'None',
                'storage': user_storages.get(largest_user_id, 0) if largest_user_id else 0
            },
            'newest_users': [{'username': u.username, 'email': u.email} for u in newest_users],
            'trend': {
                'dates': trend_dates,
                'activity': trend_activity
            },
            'registrations': {
                'dates': reg_dates,
                'counts': reg_counts
            },
            'uploads_trend': {
                'dates': upload_dates,
                'counts': upload_counts,
                'sizes': upload_sizes
            },
            'storage_growth': {
                'dates': upload_dates,
                'sizes': growth_sizes
            },
            'file_types': {
                'labels': list(types.keys()),
                'counts': list(types.values()),
                'sizes': list(type_sizes.values())
            },
            'top_consumers': top_consumers,
            'activities_grouped': activity_distribution
        }

analytics_service = AnalyticsService()
