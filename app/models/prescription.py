import json
from datetime import datetime, timezone
from app.extensions import db


class Prescription(db.Model):
    """Prescription upload and extraction record."""
    __tablename__ = "prescriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)

    original_filename = db.Column(db.String(255), default="prescription.jpg", nullable=False)
    stored_filename = db.Column("image_path", db.String(255), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)  # 'image' or 'pdf'
    file_size = db.Column(db.Integer, nullable=False)
    page_count = db.Column(db.Integer, default=1, nullable=False)

    patient_name = db.Column(db.String(150), nullable=True)
    doctor_name = db.Column(db.String(150), nullable=True)
    prescription_date = db.Column(db.String(50), nullable=True)

    status = db.Column(db.String(30), default="pending", nullable=False, index=True)  # 'pending', 'processing', 'completed', 'error'
    ocr_quality = db.Column(db.String(20), default="fair", nullable=False)  # 'good', 'fair', 'poor'
    has_unclear_fields = db.Column(db.Boolean, default=False, nullable=False)
    error_message = db.Column(db.Text, nullable=True)

    raw_ocr_text = db.Column(db.Text, nullable=True)
    gemini_raw_response = db.Column(db.Text, nullable=True)
    general_instructions_json = db.Column(db.Text, nullable=True)
    unclear_items_json = db.Column(db.Text, nullable=True)
    comparison_data_json = db.Column(db.Text, nullable=True)
    clinical_safety_json = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    medicines = db.relationship("Medicine", backref="prescription", lazy="dynamic", cascade="all, delete-orphan")
    schedules = db.relationship("Schedule", backref="prescription", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def general_instructions(self):
        if self.general_instructions_json:
            try:
                return json.loads(self.general_instructions_json)
            except Exception:
                return []
        return []

    @general_instructions.setter
    def general_instructions(self, val):
        self.general_instructions_json = json.dumps(val or [], default=str)

    @property
    def unclear_items(self):
        if self.unclear_items_json:
            try:
                return json.loads(self.unclear_items_json)
            except Exception:
                return []
        return []

    @unclear_items.setter
    def unclear_items(self, val):
        self.unclear_items_json = json.dumps(val or [], default=str)

    @property
    def comparison_data(self):
        if self.comparison_data_json:
            try:
                return json.loads(self.comparison_data_json)
            except Exception:
                return None
        return None

    @comparison_data.setter
    def comparison_data(self, val):
        self.comparison_data_json = json.dumps(val, default=str) if val else None

    @property
    def clinical_safety(self):
        if self.clinical_safety_json:
            try:
                return json.loads(self.clinical_safety_json)
            except Exception:
                return {}
        return {}

    @clinical_safety.setter
    def clinical_safety(self, val):
        self.clinical_safety_json = json.dumps(val, default=str) if val else None

    def to_dict(self):
        p_date = None
        if self.prescription_date:
            p_date = self.prescription_date.isoformat() if hasattr(self.prescription_date, "isoformat") else str(self.prescription_date)

        return {
            "id": self.id,
            "user_id": self.user_id,
            "profile_id": self.profile_id,
            "profile_name": self.profile.name if self.profile else None,
            "original_filename": self.original_filename,
            "stored_filename": self.stored_filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "page_count": self.page_count,
            "patient_name": self.patient_name,
            "doctor_name": self.doctor_name,
            "prescription_date": p_date,
            "status": self.status,
            "ocr_quality": self.ocr_quality,
            "has_unclear_fields": self.has_unclear_fields,
            "error_message": self.error_message,
            "general_instructions": self.general_instructions,
            "unclear_items": self.unclear_items,
            "comparison_data": self.comparison_data,
            "clinical_safety": self.clinical_safety,
            "medicines_count": self.medicines.count() if hasattr(self.medicines, "count") else len(self.medicines),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
