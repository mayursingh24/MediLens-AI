from datetime import datetime, timezone
from app.extensions import db


class Schedule(db.Model):
    """Medication schedule for timed reminders and adherence tracking."""
    __tablename__ = "schedules"

    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False, index=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    time_slot = db.Column(db.String(50), nullable=False)  # 'morning', 'afternoon', 'evening', 'night', 'custom'
    reminder_time = db.Column(db.String(10), nullable=False)  # HH:MM format e.g. "08:00"
    dose_amount = db.Column(db.String(100), default="1 tablet", nullable=False)
    food_instruction = db.Column(db.String(255), nullable=True)  # 'After food', 'Before food'

    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    medication_logs = db.relationship("MedicationLog", backref="schedule", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def medicine_name(self) -> str:
        return self.medicine.display_name if self.medicine else "Medicine"

    @property
    def dosage_instruction(self) -> str:
        parts = [self.dose_amount]
        if self.food_instruction:
            parts.append(self.food_instruction)
        return " &bull; ".join(parts) if parts else "as directed"

    def to_dict(self):
        return {
            "id": self.id,
            "medicine_id": self.medicine_id,
            "medicine_name": self.medicine.display_name if self.medicine else None,
            "medicine_strength": self.medicine.display_strength if self.medicine else None,
            "prescription_id": self.prescription_id,
            "profile_id": self.profile_id,
            "user_id": self.user_id,
            "time_slot": self.time_slot,
            "reminder_time": self.reminder_time,
            "dose_amount": self.dose_amount,
            "food_instruction": self.food_instruction,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
