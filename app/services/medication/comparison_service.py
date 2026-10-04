from typing import Dict, Any, List, Optional
from app.models.prescription import Prescription
from app.models.medicine import Medicine


def compare_prescriptions(current_prescription: Prescription, previous_prescription: Optional[Prescription]) -> Dict[str, Any]:
    """
    Signature 'What Changed?' Prescription Evolution Detector:
    Compares the newly uploaded prescription with the patient's prior prescription record.
    Detects:
    - Added medicines (+)
    - Discontinued / Removed medicines (-)
    - Dosage changes (↗ / ↘)
    - Duration changes
    - Frequency & timing modifications
    """
    if not previous_prescription:
        return {
            "has_previous": False,
            "message": "First baseline prescription recorded for this patient. Future uploads will display clinical diffs.",
            "added": [],
            "removed": [],
            "changed": [],
            "unchanged": []
        }

    curr_meds = current_prescription.medicines.all() if hasattr(current_prescription.medicines, "all") else list(current_prescription.medicines)
    prev_meds = previous_prescription.medicines.all() if hasattr(previous_prescription.medicines, "all") else list(previous_prescription.medicines)

    curr_dict = {m.display_name.lower().strip(): m for m in curr_meds}
    prev_dict = {m.display_name.lower().strip(): m for m in prev_meds}

    added = []
    removed = []
    changed = []
    unchanged = []

    # 1. Check for Added or Changed medicines
    for name_lower, c_med in curr_dict.items():
        # Look for exact or fuzzy match in previous
        match = None
        for p_name, p_med in prev_dict.items():
            if name_lower == p_name or (len(name_lower) > 4 and name_lower in p_name) or (len(p_name) > 4 and p_name in name_lower):
                match = p_med
                break

        if not match:
            added.append({
                "name": c_med.display_name,
                "strength": c_med.display_strength or "Unspecified",
                "dosage": c_med.display_dosage or "1 dose",
                "frequency": c_med.display_frequency or "Unspecified",
                "duration_days": c_med.display_duration_days or "Course",
                "type": "added"
            })
        else:
            diffs = []
            # Compare dosage
            if (c_med.display_dosage or "").strip() != (match.display_dosage or "").strip() and (c_med.display_dosage and match.display_dosage):
                diffs.append({
                    "field": "Dose",
                    "old": match.display_dosage,
                    "new": c_med.display_dosage,
                    "icon": "↗"
                })

            # Compare frequency / schedule
            if (c_med.display_frequency or "").strip() != (match.display_frequency or "").strip() and (c_med.display_frequency and match.display_frequency):
                diffs.append({
                    "field": "Frequency",
                    "old": match.display_frequency,
                    "new": c_med.display_frequency,
                    "icon": "⏱"
                })

            # Compare duration
            if c_med.display_duration_days and match.display_duration_days and c_med.display_duration_days != match.display_duration_days:
                diffs.append({
                    "field": "Duration",
                    "old": f"{match.display_duration_days} days",
                    "new": f"{c_med.display_duration_days} days",
                    "icon": "📅"
                })

            # Compare strength
            if (c_med.display_strength or "").strip() != (match.display_strength or "").strip() and (c_med.display_strength and match.display_strength):
                diffs.append({
                    "field": "Strength",
                    "old": match.display_strength,
                    "new": c_med.display_strength,
                    "icon": "⚡"
                })

            if diffs:
                changed.append({
                    "name": c_med.display_name,
                    "diffs": diffs,
                    "type": "changed"
                })
            else:
                unchanged.append(c_med.display_name)

    # 2. Check for Removed / Discontinued medicines
    for name_lower, p_med in prev_dict.items():
        matched = False
        for c_name in curr_dict.keys():
            if name_lower == c_name or (len(name_lower) > 4 and name_lower in c_name) or (len(c_name) > 4 and c_name in name_lower):
                matched = True
                break
        if not matched:
            removed.append({
                "name": p_med.display_name,
                "strength": p_med.display_strength or "Unspecified",
                "dosage": p_med.display_dosage or "1 dose",
                "duration_days": p_med.display_duration_days or "Course",
                "type": "removed"
            })

    summary_parts = []
    if added:
        summary_parts.append(f"{len(added)} new medication{'s' if len(added)>1 else ''} added")
    if removed:
        summary_parts.append(f"{len(removed)} discontinued")
    if changed:
        summary_parts.append(f"{len(changed)} modified in dose or duration")
    if not (added or removed or changed):
        summary_parts.append("Medications unchanged from previous prescription")

    prev_date = ""
    if previous_prescription.prescription_date:
        prev_date = (
            previous_prescription.prescription_date.isoformat()
            if hasattr(previous_prescription.prescription_date, "isoformat")
            else str(previous_prescription.prescription_date)
        )
    elif previous_prescription.created_at:
        prev_date = previous_prescription.created_at.strftime("%d %b %Y")

    return {
        "has_previous": True,
        "previous_prescription_id": previous_prescription.id,
        "previous_prescription_filename": previous_prescription.original_filename,
        "previous_prescription_date": prev_date,
        "summary": " • ".join(summary_parts),
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
    }
