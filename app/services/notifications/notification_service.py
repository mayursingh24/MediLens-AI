from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from app.models.notification import Notification
from app.extensions import db


def create_notification(
    user_id: int,
    title: str,
    message: str,
    notification_type: str = "medicine_reminder",
    profile_id: Optional[int] = None,
    prescription_id: Optional[int] = None,
    schedule_id: Optional[int] = None,
    scheduled_for: Optional[datetime] = None
) -> Notification:
    """Create and persist a new notification record."""
    notif = Notification(
        user_id=user_id,
        profile_id=profile_id,
        prescription_id=prescription_id,
        schedule_id=schedule_id,
        title=title,
        message=message,
        notification_type=notification_type,
        status="unread",
        scheduled_for=scheduled_for or datetime.now(timezone.utc),
    )
    db.session.add(notif)
    db.session.commit()
    return notif


def get_user_notifications(user_id: int, status: Optional[str] = None, limit: int = 25) -> List[Notification]:
    """Retrieve notifications for a user."""
    query = Notification.query.filter_by(user_id=user_id)
    if status:
        query = query.filter_by(status=status)
    return query.order_by(Notification.created_at.desc()).limit(limit).all()


def mark_notification_as_read(notification_id: int, user_id: int) -> bool:
    """Mark a notification as read."""
    notif = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
    if notif:
        notif.status = "read"
        db.session.commit()
        return True
    return False


def snooze_notification(notification_id: int, user_id: int, snooze_minutes: int = 15) -> Optional[Notification]:
    """Snooze a notification for a specified number of minutes."""
    notif = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
    if notif:
        notif.status = "snoozed"
        notif.scheduled_for = datetime.now(timezone.utc) + timedelta(minutes=snooze_minutes)
        db.session.commit()
        return notif
    return None
