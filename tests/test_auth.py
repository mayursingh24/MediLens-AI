import pytest
from app.utils.validators import validate_email, validate_password
from app.models.user import User


def test_validate_email():
    """Verify email validation rules."""
    assert validate_email("patient@example.com") is True
    assert validate_email("doctor.sharma@hospital.org") is True
    assert validate_email("invalid-email") is False
    assert validate_email("") is False
    assert validate_email(None) is False


def test_validate_password():
    """Verify strong password requirements."""
    # Valid passwords
    valid, err = validate_password("SecurePass123")
    assert valid is True
    assert err is None

    # Too short
    valid, err = validate_password("Short1")
    assert valid is False
    assert "8 characters" in err

    # Missing number
    valid, err = validate_password("PasswordWithoutNumber")
    assert valid is False
    assert "number" in err

    # Missing letters
    valid, err = validate_password("123456789")
    assert valid is False
    assert "letter" in err


def test_user_password_hashing():
    """Verify user model password hashing and verification."""
    user = User(email="test@medilens.ai", full_name="Test User")
    user.set_password("MySecretPass2026")

    assert user.password_hash != "MySecretPass2026"
    assert user.check_password("MySecretPass2026") is True
    assert user.check_password("WrongPassword") is False
