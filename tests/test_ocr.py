import pytest
from app.services.ocr.ocr_validator import validate_ocr_result, PRESCRIPTION_UNREADABLE_MESSAGE


def test_ocr_validator_readable_text():
    """Verify OCR validation accepts clear text."""
    ocr_data = {
        "text": "Rx Dr. Mehta Paracetamol 650mg TDS for 5 days after meal",
        "mean_confidence": 88.5,
        "word_count": 10
    }
    is_readable, msg = validate_ocr_result(ocr_data)
    assert is_readable is True
    assert msg == ""


def test_ocr_validator_rejects_empty():
    """Verify empty OCR text triggers clinical error message."""
    ocr_data = {
        "text": "",
        "mean_confidence": 0.0,
        "word_count": 0
    }
    is_readable, msg = validate_ocr_result(ocr_data)
    assert is_readable is False
    assert msg == PRESCRIPTION_UNREADABLE_MESSAGE


def test_ocr_validator_rejects_noise():
    """Verify non-alphanumeric noise triggers unreadable error."""
    ocr_data = {
        "text": "--- ... /// ::: ???",
        "mean_confidence": 10.0,
        "word_count": 5
    }
    is_readable, msg = validate_ocr_result(ocr_data)
    assert is_readable is False
    assert msg == PRESCRIPTION_UNREADABLE_MESSAGE
