from datetime import date, timedelta
from typing import List, Dict, Any, Optional
from app.models.medicine import Medicine
from app.models.schedule import Schedule
from app.extensions import db


# Default recommended reminder times
DEFAULT_SLOT_TIMES = {
    "morning": "08:00",
    "afternoon": "13:00",
    "evening": "18:00",
    "night": "21:00",
}


def generate_schedules_for_medicine(
    medicine: Medicine,
    user_id: int,
    custom_times: Optional[Dict[str, str]] = None,
    start_date: Optional[date] = None
) -> List[Schedule]:
    """
    Generate medication schedule items based on medicine's dosage and frequency.
    Ensures prescribed frequencies are strictly respected while honoring user-selected times.
    """
    schedules = []
    slot_times = DEFAULT_SLOT_TIMES.copy()
    if custom_times:
        slot_times.update(custom_times)

    effective_start = start_date or date.today()
    duration = medicine.display_duration_days
    effective_end = (effective_start + timedelta(days=duration - 1)) if duration and duration > 0 else None

    # Check each timing slot
    slots = [
        ("morning", medicine.verified_morning if (medicine.is_user_verified and medicine.verified_morning is not None) else medicine.morning),
        ("afternoon", medicine.verified_afternoon if (medicine.is_user_verified and medicine.verified_afternoon is not None) else medicine.afternoon),
        ("evening", medicine.verified_evening if (medicine.is_user_verified and medicine.verified_evening is not None) else medicine.evening),
        ("night", medicine.verified_night if (medicine.is_user_verified and medicine.verified_night is not None) else medicine.night),
    ]

    form_label = medicine.display_form or "unit"
    food = medicine.display_food_instruction or ""

    has_specific_slots = False
    for slot_name, dose in slots:
        if dose and dose > 0:
            has_specific_slots = True
            dose_str = f"{int(dose) if dose.is_integer() else dose} {form_label}"
            sched = Schedule(
                medicine_id=medicine.id,
                prescription_id=medicine.prescription_id,
                profile_id=medicine.profile_id,
                user_id=user_id,
                time_slot=slot_name,
                reminder_time=slot_times.get(slot_name, "08:00"),
                dose_amount=dose_str,
                food_instruction=food,
                start_date=effective_start,
                end_date=effective_end,
                is_active=True,
            )
            schedules.append(sched)

    # Fallback if specific numeric dose slots were missing, parse frequency notation directly
    if not has_specific_slots:
        freq = (medicine.display_frequency or "").lower().replace(" ", "")
        if "1-0-1" in freq or "bd" in freq or "bid" in freq or "twice" in freq or "2times" in freq:
            target_slots = [("morning", slot_times["morning"]), ("night", slot_times["night"])]
        elif "1-1-1" in freq or "tds" in freq or "tid" in freq or "thrice" in freq or "3times" in freq:
            target_slots = [("morning", slot_times["morning"]), ("afternoon", slot_times["afternoon"]), ("night", slot_times["night"])]
        elif "0-0-1" in freq or "hs" in freq or "bedtime" in freq or "night" in freq:
            target_slots = [("night", slot_times["night"])]
        elif "0-1-0" in freq or "noon" in freq or "afternoon" in freq:
            target_slots = [("afternoon", slot_times["afternoon"])]
        elif "1-1-1-1" in freq or "qid" in freq or "4times" in freq:
            target_slots = [("morning", slot_times["morning"]), ("afternoon", slot_times["afternoon"]), ("evening", slot_times["evening"]), ("night", slot_times["night"])]
        else:
            # Default standard single daily morning dose
            target_slots = [("morning", slot_times["morning"])]

        for s_name, s_time in target_slots:
            schedules.append(Schedule(
                medicine_id=medicine.id,
                prescription_id=medicine.prescription_id,
                profile_id=medicine.profile_id,
                user_id=user_id,
                time_slot=s_name,
                reminder_time=s_time,
                dose_amount=f"1 {form_label}",
                food_instruction=food or "After food",
                start_date=effective_start,
                end_date=effective_end,
                is_active=True,
            ))

    return schedules


def save_schedules_for_prescription(prescription, user_id: int) -> List[Schedule]:
    """Regenerate and commit active schedules for all confirmed medicines in a prescription."""
    # Remove existing schedules for this prescription to avoid duplication
    Schedule.query.filter_by(prescription_id=prescription.id).delete()

    created = []
    for med in prescription.medicines:
        schedules = generate_schedules_for_medicine(med, user_id=user_id)
        for s in schedules:
            db.session.add(s)
            created.append(s)

    db.session.commit()
    return created
