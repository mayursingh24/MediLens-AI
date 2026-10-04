from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class User(db.Model):
    """User account model."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(191), unique=True, nullable=False, index=True)
    password_hash = db.Column("password", db.String(255), nullable=False)
    full_name = db.Column("name", db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    preferred_language = db.Column(db.String(10), default="en", nullable=False)  # 'en', 'hi', 'hinglish'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    profiles = db.relationship("Profile", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    prescriptions = db.relationship("Prescription", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password: str):
        """Hash and set user password."""
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password: str) -> bool:
        """Verify user password."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Serialize user to dictionary (excluding sensitive fields)."""
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "preferred_language": self.preferred_language,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
