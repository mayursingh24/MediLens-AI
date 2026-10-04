import pytest
from app.utils.json_parser import parse_and_validate_gemini_prescription, extract_json_block


def test_extract_json_block():
    """Verify stripping markdown code fences."""
    raw = "```json\n{\"patient_name\": \"John Doe\"}\n```"
    extracted = extract_json_block(raw)
    assert extracted == '{"patient_name": "John Doe"}'

    raw_no_fences = '{"patient_name": "John Doe"}'
    assert extract_json_block(raw_no_fences) == '{"patient_name": "John Doe"}'


def test_parse_valid_gemini_prescription():
    """Verify parsing valid Gemini prescription schema."""
    sample_response = """```json
    {
      "patient_name": "Rohan Sharma",
      "doctor_name": "Dr. A. Verma",
      "prescription_date": "2026-10-01",
      "medicines": [
        {
          "name": "Amoxicillin",
          "strength": "500 mg",
          "form": "Capsule",
          "dosage": "1 capsule",
          "frequency": "1-0-1",
          "morning": 1,
          "afternoon": 0,
          "evening": 0,
          "night": 1,
          "duration_days": 5,
          "food_instruction": "After food",
          "special_instruction": "Complete full course",
          "quantity": 10,
          "confidence": 95,
          "verification_status": "verified"
        }
      ],
      "general_instructions": ["Drink plenty of warm water"],
      "unclear_items": []
    }
    ```"""

    parsed = parse_and_validate_gemini_prescription(sample_response)
    assert parsed["patient_name"] == "Rohan Sharma"
    assert parsed["doctor_name"] == "Dr. A. Verma"
    assert len(parsed["medicines"]) == 1
    med = parsed["medicines"][0]
    assert med["name"] == "Amoxicillin"
    assert med["morning"] == 1.0
    assert med["night"] == 1.0
    assert med["duration_days"] == 5
    assert med["confidence"] == 95.0


def test_parse_invalid_json():
    """Verify invalid JSON raises ValueError."""
    with pytest.raises(ValueError):
        parse_and_validate_gemini_prescription("This is not JSON text")
