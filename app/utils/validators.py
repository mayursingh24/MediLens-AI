import re
from typing import Tuple, Optional


EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")


def validate_email(email: str) -> bool:
    """Validate email format."""
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate password strength:
    - Minimum 8 characters
    - At least one letter
    - At least one digit
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not any(char.isdigit() for char in password):
        return False, "Password must contain at least one number."
    if not any(char.isalpha() for char in password):
        return False, "Password must contain at least one letter."
    return True, None


def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """Check if filename has an allowed extension."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in allowed_extensions


def validate_medicine_name(name: str) -> bool:
    """Check that medicine name is a valid non-empty string."""
    if not name or not isinstance(name, str):
        return False
    cleaned = name.strip()
    return len(cleaned) >= 2 and len(cleaned) <= 255


def validate_dosage_values(morning, afternoon, evening, night) -> Tuple[float, float, float, float]:
    """Coerce and validate numeric dosage numbers."""
    def _coerce(val):
        try:
            v = float(val)
            return max(0.0, v)
        except (ValueError, TypeError):
            return 0.0
    return _coerce(morning), _coerce(afternoon), _coerce(evening), _coerce(night)
