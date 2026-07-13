from app import db
from app.models import Notification
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def create_notification(user_id, title, message, notification_type, icon='bi-bell', action_url=None):
        try:
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=notification_type,
                icon=icon,
                action_url=action_url
            )
            db.session.add(notification)
            db.session.commit()
            return notification
        except Exception as e:
            logger.error(f"Failed to create notification for user {user_id}: {str(e)}")
            db.session.rollback()
            return None

notification_service = NotificationService()
