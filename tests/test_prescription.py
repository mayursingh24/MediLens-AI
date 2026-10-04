import pytest
from app.utils.validators import validate_file_extension
from app.services.ai.extraction_validator import cross_validate_medicine, calculate_similarity
from app.services.ai.safety_engine import run_prescription_safety_checks


def test_file_extension_validation():
    """Verify file extension validator."""
    allowed = {"png", "jpg", "jpeg", "pdf"}
    assert validate_file_extension("prescription.pdf", allowed) is True
    assert validate_file_extension("scan.jpg", allowed) is True
    assert validate_file_extension("photo.PNG", allowed) is True
    assert validate_file_extension("malicious.exe", allowed) is False
    assert validate_file_extension("script.sh", allowed) is False
    assert validate_file_extension("no_extension", allowed) is False


def test_string_similarity():
    """Verify string similarity calculation for cross-validation."""
    sim_exact = calculate_similarity("Paracetamol", "Paracetamol")
    assert sim_exact == 1.0

    sim_typo = calculate_similarity("Paracitamol", "Paracetamol")
    assert sim_typo > 0.85

    sim_different = calculate_similarity("Metformin", "Amlodipine")
    assert sim_different < 0.50


def test_cross_validation_high_confidence():
    """Verify cross-validation passes when OCR and Gemini match."""
    medicine = {
        "name": "Paracetamol",
        "strength": "500 mg",
        "dosage": "1 tablet",
        "confidence": 95.0,
        "verification_status": "verified"
    }
    raw_ocr = "Rx Dr. Sharma Paracetamol 500mg 1 tab after food"

    validated = cross_validate_medicine(medicine, raw_ocr, ocr_quality="good")
    assert validated["verification_status"] == "verified"
    assert validated["confidence"] >= 90.0
    assert "High confidence match" in validated["conflict_details"]


def test_cross_validation_conflict_detection():
    """Verify conflict warning when Gemini and OCR diverge."""
    medicine = {
        "name": "Azithromycin",
        "strength": "500 mg",
        "dosage": "1 tablet",
        "confidence": 85.0,
        "verification_status": "verified"
    }
    raw_ocr = "Rx Dr. Sharma Ibuprofen 400mg twice daily"

    validated = cross_validate_medicine(medicine, raw_ocr, ocr_quality="good")
    assert validated["verification_status"] == "review_required"
    assert "Verification Required" in validated["conflict_details"]


def test_safety_engine_unclear_medicine():
    """Verify safety engine flags unclear medicines without guessing."""
    medicines = [
        {
            "name": "unclear",
            "strength": "",
            "dosage": "",
            "frequency": "",
            "verification_status": "unclear"
        }
    ]
    alerts = run_prescription_safety_checks(medicines)
    assert len(alerts) > 0
    unclear_alerts = [a for a in alerts if a["type"] == "unclear_medicine"]
    assert len(unclear_alerts) == 1
    assert "Handwriting or name could not be confirmed" in unclear_alerts[0]["message"]


def test_date_json_serialization_in_models():
    """Verify that datetime.date and datetime.datetime objects serialize cleanly without throwing TypeError."""
    import datetime
    from app.models.prescription import Prescription
    from app.models.medicine import Medicine
    from app.models.audit_log import AuditLog
    from app.services.medication.comparison_service import compare_prescriptions

    today = datetime.date.today()
    now = datetime.datetime.now()

    # 1. Prescription comparison_data setter with dates
    p = Prescription()
    p.comparison_data = {
        "prescription_date": today,
        "created_at": now,
        "nested": {"nested_date": today}
    }
    assert p.comparison_data is not None
    assert str(today) in p.comparison_data_json

    # 2. Prescription clinical_safety setter with dates
    p.clinical_safety = {
        "assessment_date": today,
        "warnings": ["Take with food"]
    }
    assert p.clinical_safety is not None

    # 3. Medicine external intelligence with dates
    m = Medicine()
    m.external_intelligence = {"fetched_at": today}
    assert m.external_intelligence["fetched_at"] == str(today)

    # 4. AuditLog with dates in details
    log = AuditLog()
    log.details = {"event_date": today}
    assert log.details["event_date"] == str(today)

    # 5. compare_prescriptions with previous prescription having date object
    prev = Prescription()
    prev.id = 1
    prev.original_filename = "prev.jpg"
    prev.prescription_date = today
    prev.created_at = now

    curr = Prescription()
    curr.id = 2
    curr.original_filename = "curr.jpg"

    diff = compare_prescriptions(curr, prev)
    assert diff["has_previous"] is True
    assert isinstance(diff["previous_prescription_date"], str)

    # Setting diff to curr.comparison_data must succeed without error
    curr.comparison_data = diff
    assert curr.comparison_data is not None

