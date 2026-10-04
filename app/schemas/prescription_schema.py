from app.schemas.medicine_schema import serialize_medicine


def serialize_prescription(prescription, include_medicines: bool = True):
    """Serialize a Prescription model instance."""
    if not prescription:
        return {}

    data = {
        "id": prescription.id,
        "user_id": prescription.user_id,
        "profile_id": prescription.profile_id,
        "profile_name": prescription.profile.name if prescription.profile else None,
        "original_filename": prescription.original_filename,
        "stored_filename": prescription.stored_filename,
        "file_type": prescription.file_type,
        "file_size": prescription.file_size,
        "page_count": prescription.page_count,
        "patient_name": prescription.patient_name,
        "doctor_name": prescription.doctor_name,
        "prescription_date": prescription.prescription_date,
        "status": prescription.status,
        "ocr_quality": prescription.ocr_quality,
        "has_unclear_fields": prescription.has_unclear_fields,
        "error_message": prescription.error_message,
        "general_instructions": prescription.general_instructions,
        "unclear_items": prescription.unclear_items,
        "created_at": prescription.created_at.isoformat() if prescription.created_at else None,
    }

    if include_medicines:
        data["medicines"] = [serialize_medicine(m) for m in prescription.medicines]
    return data
