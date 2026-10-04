def serialize_medicine(med):
    """Serialize a Medicine model instance with extraction vs verification tracking."""
    if not med:
        return {}
    return {
        "id": med.id,
        "prescription_id": med.prescription_id,
        "profile_id": med.profile_id,
        # Original AI extraction
        "original_ai": {
            "name": med.name,
            "strength": med.strength,
            "form": med.form,
            "dosage": med.dosage,
            "frequency": med.frequency,
            "morning": med.morning,
            "afternoon": med.afternoon,
            "evening": med.evening,
            "night": med.night,
            "duration_days": med.duration_days,
            "food_instruction": med.food_instruction,
            "special_instruction": med.special_instruction,
            "quantity": med.quantity,
        },
        # Quality & Cross-validation
        "confidence": med.confidence,
        "verification_status": med.verification_status,
        "ocr_extracted_text": med.ocr_extracted_text,
        "gemini_extracted_text": med.gemini_extracted_text,
        "conflict_details": med.conflict_details,
        "source_page": med.source_page,
        # Human verification
        "is_user_verified": med.is_user_verified,
        "verified_data": {
            "name": med.verified_name,
            "strength": med.verified_strength,
            "form": med.verified_form,
            "dosage": med.verified_dosage,
            "frequency": med.verified_frequency,
            "morning": med.verified_morning,
            "afternoon": med.verified_afternoon,
            "evening": med.verified_evening,
            "night": med.verified_night,
            "duration_days": med.verified_duration_days,
            "food_instruction": med.verified_food_instruction,
            "notes": med.verification_notes,
            "verified_at": med.verified_at.isoformat() if med.verified_at else None,
        },
        # Display/effective values
        "display": {
            "name": med.display_name,
            "strength": med.display_strength,
            "form": med.display_form,
            "dosage": med.display_dosage,
            "frequency": med.display_frequency,
            "duration_days": med.display_duration_days,
            "food_instruction": med.display_food_instruction,
        },
        "created_at": med.created_at.isoformat() if med.created_at else None,
    }
