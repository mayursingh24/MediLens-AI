from datetime import datetime, timezone
from app.extensions import db


class Profile(db.Model):
    """Family / Patient Profile model."""
    __tablename__ = "profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    relationship = db.Column(db.String(50), default="Me", nullable=False)  # 'Me', 'Father', 'Mother', 'Grandparent', 'Child', 'Custom'
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(20), nullable=True)  # 'Male', 'Female', 'Other'
    weight_kg = db.Column(db.Float, nullable=True)
    allergies_json = db.Column(db.Text, nullable=True)
    existing_conditions_json = db.Column(db.Text, nullable=True)
    existing_medications_json = db.Column(db.Text, nullable=True)
    pregnancy_status = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    prescriptions = db.relationship("Prescription", backref="profile", lazy="dynamic", cascade="all, delete-orphan")
    schedules = db.relationship("Schedule", backref="profile", lazy="dynamic", cascade="all, delete-orphan")
    medication_logs = db.relationship("MedicationLog", backref="profile", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def age_category(self) -> str:
        """Clinically relevant age bracket for dosing decisions."""
        if self.age is None:
            return "adult"
        if self.age < 18:
            return "pediatric"
        if self.age >= 65:
            return "older_adult"
        return "adult"

    @property
    def allergies(self):
        import json
        if self.allergies_json:
            try:
                return json.loads(self.allergies_json)
            except Exception:
                return []
        return []

    @allergies.setter
    def allergies(self, val):
        import json
        self.allergies_json = json.dumps(val, default=str) if val else None

    @property
    def existing_conditions(self):
        import json
        if self.existing_conditions_json:
            try:
                return json.loads(self.existing_conditions_json)
            except Exception:
                return []
        return []

    @existing_conditions.setter
    def existing_conditions(self, val):
        import json
        self.existing_conditions_json = json.dumps(val, default=str) if val else None

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "relationship": self.relationship,
            "age": self.age,
            "gender": self.gender,
            "weight_kg": self.weight_kg,
            "age_category": self.age_category,
            "allergies": self.allergies,
            "existing_conditions": self.existing_conditions,
            "pregnancy_status": self.pregnancy_status,
            "notes": self.notes,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
