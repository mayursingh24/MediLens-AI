from datetime import datetime, timezone
from app.extensions import db


class MedicationLog(db.Model):
    """Adherence log for recording taken, skipped, and missed doses."""
    __tablename__ = "medication_logs"

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False, index=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    scheduled_time = db.Column(db.String(10), nullable=False)  # HH:MM format
    action = db.Column(db.String(20), nullable=False, index=True)  # 'taken', 'skipped', 'snoozed', 'missed'
    logged_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    notes = db.Column(db.Text, nullable=True)

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
            "schedule_id": self.schedule_id,
            "medicine_id": self.medicine_id,
            "medicine_name": self.medicine.display_name if self.medicine else None,
            "profile_id": self.profile_id,
            "user_id": self.user_id,
            "scheduled_date": self.scheduled_date.isoformat() if self.scheduled_date else None,
            "scheduled_time": self.scheduled_time,
            "action": self.action,
            "logged_at": self.logged_at.isoformat() if self.logged_at else None,
            "notes": self.notes,
        }
