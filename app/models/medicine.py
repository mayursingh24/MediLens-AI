from datetime import datetime, timezone
from app.extensions import db


class Medicine(db.Model):
    """Prescribed medicine model with original AI extraction and human verification records."""
    __tablename__ = "medicines"

    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)

    # Original AI Extraction (Immutable once extracted)
    name = db.Column("medicine_name", db.String(255), nullable=False)
    duration = db.Column(db.String(100), nullable=True)
    strength = db.Column(db.String(100), nullable=True)
    form = db.Column(db.String(100), nullable=True)  # Tablet, Syrup, Capsule, Injection, etc.
    dosage = db.Column(db.String(100), nullable=True)
    frequency = db.Column(db.String(100), nullable=True)  # '1-0-1', 'Once daily', etc.

    morning = db.Column(db.Float, default=0.0, nullable=False)
    afternoon = db.Column(db.Float, default=0.0, nullable=False)
    evening = db.Column(db.Float, default=0.0, nullable=False)
    night = db.Column(db.Float, default=0.0, nullable=False)

    duration_days = db.Column(db.Integer, nullable=True)
    food_instruction = db.Column(db.String(255), nullable=True)  # 'After food', 'Before food', etc.
    special_instruction = db.Column(db.Text, nullable=True)
    quantity = db.Column(db.Integer, nullable=True)
    is_in_shopping_list = db.Column(db.Boolean, default=True, nullable=False)
    is_purchased = db.Column(db.Boolean, default=False, nullable=False)

    # Confidence and Cross-Validation
    confidence = db.Column(db.Float, default=0.0, nullable=False)  # Overall 0 to 100
    confidence_breakdown_json = db.Column(db.Text, nullable=True)  # Stores independent scores: {medicine, strength, dose, frequency, duration}
    verification_status = db.Column(db.String(50), default="review_required", nullable=False)  # 'verified', 'review_required', 'unclear'
    ocr_extracted_text = db.Column(db.Text, nullable=True)
    gemini_extracted_text = db.Column(db.Text, nullable=True)
    conflict_details = db.Column(db.Text, nullable=True)
    source_page = db.Column(db.Integer, default=1, nullable=False)

    # Real Medicine Intelligence & Explanations
    generic_name = db.Column(db.Text, nullable=True)
    brand_name = db.Column(db.Text, nullable=True)
    external_intelligence_json = db.Column(db.Text, nullable=True)  # Real OpenFDA/DailyMed/RxNorm data
    why_taking_this = db.Column(db.Text, nullable=True)  # "Why am I taking this?" synthesis
    dietary_guidelines_json = db.Column(db.Text, nullable=True)  # Food to eat & avoid (Kya khayein aur kya na khayein)
    estimated_price_json = db.Column(db.Text, nullable=True)  # Real verified generic pricing

    # Human Verified Values (Never overwrite the original AI extraction)
    is_user_verified = db.Column(db.Boolean, default=False, nullable=False)
    verified_name = db.Column(db.String(255), nullable=True)
    verified_strength = db.Column(db.String(100), nullable=True)
    verified_form = db.Column(db.String(100), nullable=True)
    verified_dosage = db.Column(db.String(100), nullable=True)
    verified_frequency = db.Column(db.String(100), nullable=True)
    verified_morning = db.Column(db.Float, nullable=True)
    verified_afternoon = db.Column(db.Float, nullable=True)
    verified_evening = db.Column(db.Float, nullable=True)
    verified_night = db.Column(db.Float, nullable=True)
    verified_duration_days = db.Column(db.Integer, nullable=True)
    verified_food_instruction = db.Column(db.String(255), nullable=True)
    verification_notes = db.Column(db.Text, nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    schedules = db.relationship("Schedule", backref="medicine", lazy="dynamic", cascade="all, delete-orphan")
    medication_logs = db.relationship("MedicationLog", backref="medicine", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def display_name(self):
        return self.verified_name if (self.is_user_verified and self.verified_name) else self.name

    @property
    def display_strength(self):
        return self.verified_strength if (self.is_user_verified and self.verified_strength) else self.strength

    @property
    def display_form(self):
        return self.verified_form if (self.is_user_verified and self.verified_form) else self.form

    @property
    def display_dosage(self):
        if self.is_user_verified and self.verified_dosage:
            return self.verified_dosage
        if self.dosage:
            return self.dosage
        m = self.morning or self.afternoon or self.evening or self.night or 1.0
        form = self.display_form or "Tablet"
        return f"{int(m) if isinstance(m, (int, float)) and m.is_integer() else m} {form}"

    @property
    def display_frequency(self):
        if self.is_user_verified and self.verified_frequency:
            return self.verified_frequency
        if self.frequency:
            return self.frequency
        return f"{int(self.morning or 1)}-{int(self.afternoon or 0)}-{int(self.night or 0)}"

    @property
    def display_duration_days(self):
        if self.is_user_verified and self.verified_duration_days is not None:
            return self.verified_duration_days
        return self.duration_days or 5

    @property
    def display_food_instruction(self):
        if self.is_user_verified and self.verified_food_instruction:
            return self.verified_food_instruction
        if self.food_instruction:
            return self.food_instruction
        name_lower = (self.name or "").lower()
        if any(ppi in name_lower for ppi in ["panto", "omeprazole", "rabeprazole", "esomeprazole", "pan-", "antacid"]):
            return "Before food (Empty stomach)"
        return "After food"

    @property
    def confidence_breakdown(self):
        import json
        if self.confidence_breakdown_json:
            try:
                return json.loads(self.confidence_breakdown_json)
            except Exception:
                pass
        # Fallback default breakdown based on overall confidence
        c = int(self.confidence) if self.confidence else 85
        return {
            "medicine": max(60, min(99, c)),
            "strength": max(55, min(98, c - 2)),
            "dose": max(50, min(96, c - 4)),
            "frequency": max(50, min(95, c - 3)),
            "duration": max(45, min(92, c - 8))
        }

    @confidence_breakdown.setter
    def confidence_breakdown(self, val):
        import json
        self.confidence_breakdown_json = json.dumps(val, default=str) if val else None

    @property
    def external_intelligence(self):
        import json
        if self.external_intelligence_json:
            try:
                return json.loads(self.external_intelligence_json)
            except Exception:
                return None
        return None

    @external_intelligence.setter
    def external_intelligence(self, val):
        import json
        self.external_intelligence_json = json.dumps(val, default=str) if val else None

    @property
    def dietary_guidelines(self):
        import json
        if self.dietary_guidelines_json:
            try:
                return json.loads(self.dietary_guidelines_json)
            except Exception:
                return None
        return None

    @dietary_guidelines.setter
    def dietary_guidelines(self, val):
        import json
        self.dietary_guidelines_json = json.dumps(val, default=str) if val else None

    @property
    def estimated_price(self):
        import json
        if self.estimated_price_json:
            try:
                return json.loads(self.estimated_price_json)
            except Exception:
                return None
        return None

    @estimated_price.setter
    def estimated_price(self, val):
        import json
        self.estimated_price_json = json.dumps(val, default=str) if val else None

    def to_dict(self):
        return {
            "id": self.id,
            "prescription_id": self.prescription_id,
            "profile_id": self.profile_id,
            "name": self.name,
            "generic_name": self.generic_name,
            "brand_name": self.brand_name,
            "strength": self.strength,
            "form": self.form,
            "dosage": self.dosage,
            "frequency": self.frequency,
            "morning": self.morning,
            "afternoon": self.afternoon,
            "evening": self.evening,
            "night": self.night,
            "duration_days": self.duration_days,
            "food_instruction": self.food_instruction,
            "special_instruction": self.special_instruction,
            "quantity": self.quantity,
            "is_in_shopping_list": self.is_in_shopping_list,
            "is_purchased": self.is_purchased,
            "confidence": self.confidence,
            "confidence_breakdown": self.confidence_breakdown,
            "verification_status": self.verification_status,
            "why_taking_this": self.why_taking_this,
            "external_intelligence": self.external_intelligence,
            "estimated_price": self.estimated_price,
            "ocr_extracted_text": self.ocr_extracted_text,
            "gemini_extracted_text": self.gemini_extracted_text,
            "conflict_details": self.conflict_details,
            "source_page": self.source_page,
            # Verified items
            "is_user_verified": self.is_user_verified,
            "verified_name": self.verified_name,
            "verified_strength": self.verified_strength,
            "verified_form": self.verified_form,
            "verified_dosage": self.verified_dosage,
            "verified_frequency": self.verified_frequency,
            "verified_morning": self.verified_morning,
            "verified_afternoon": self.verified_afternoon,
            "verified_evening": self.verified_evening,
            "verified_night": self.verified_night,
            "verified_duration_days": self.verified_duration_days,
            "verified_food_instruction": self.verified_food_instruction,
            "verification_notes": self.verification_notes,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            # Effective display values
            "display_name": self.display_name,
            "display_strength": self.display_strength,
            "display_form": self.display_form,
            "display_dosage": self.display_dosage,
            "display_frequency": self.display_frequency,
            "display_duration_days": self.display_duration_days,
            "display_food_instruction": self.display_food_instruction,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
