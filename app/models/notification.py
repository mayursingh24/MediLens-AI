from datetime import datetime, timezone
from app.extensions import db


class Notification(db.Model):
    """User notifications model."""
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedules.id", ondelete="CASCADE"), nullable=True)

    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(
        db.String(50),
        default="medicine_reminder",
        nullable=False,
        index=True
    )  # 'medicine_reminder', 'verification_required', 'prescription_processing_complete', 'schedule_reminder'
    status = db.Column(db.String(20), default="unread", nullable=False, index=True)  # 'unread', 'read', 'snoozed'
    scheduled_for = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "profile_id": self.profile_id,
            "prescription_id": self.prescription_id,
            "schedule_id": self.schedule_id,
            "title": self.title,
            "message": self.message,
            "notification_type": self.notification_type,
            "status": self.status,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
