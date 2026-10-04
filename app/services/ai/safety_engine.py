from typing import List, Dict, Any


SAFETY_DISCLAIMER = "⚠️ Please verify all prescription details and dosages with your doctor or pharmacist."


def run_prescription_safety_checks(medicines: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Scan medicines list for clinical safety considerations:
    - Missing dosage or frequency
    - Unclear handwriting flags
    - Potential duplicate medications or similar active names
    - Missing duration
    Never declares 'safe' or 'stop medicine' — provides helpful advisory alerts.
    """
    alerts = []
    seen_names = {}

    for idx, med in enumerate(medicines, start=1):
        name = (med.get("display_name") or med.get("name") or "").strip().lower()
        strength = (med.get("display_strength") or med.get("strength") or "").strip()
        dosage = (med.get("display_dosage") or med.get("dosage") or "").strip()
        frequency = (med.get("display_frequency") or med.get("frequency") or "").strip()
        duration = med.get("display_duration_days") or med.get("duration_days")
        status = med.get("verification_status")

        # 1. Unclear medicine handwriting
        if status in {"unclear", "review_required"} or not name or name in {"unclear", "unknown", "illegible"}:
            alerts.append({
                "type": "unclear_medicine",
                "severity": "high",
                "medicine_name": name or "Unknown item",
                "message": f"Medicine #{idx} ({name or 'Unreadable'}): Handwriting or name could not be confirmed with certainty. {SAFETY_DISCLAIMER}"
            })

        # 2. Missing frequency
        if not frequency or frequency.lower() in {"unknown", "as directed", "prn"}:
            alerts.append({
                "type": "missing_frequency",
                "severity": "medium",
                "medicine_name": name,
                "message": f"'{name}': Specific timing frequency is not explicitly defined in prescription. Confirm interval with pharmacist."
            })

        # 3. Missing dosage
        if not dosage and not (med.get("morning") or med.get("afternoon") or med.get("evening") or med.get("night")):
            alerts.append({
                "type": "missing_dosage",
                "severity": "medium",
                "medicine_name": name,
                "message": f"'{name}': Specific dosage count per administration is missing. Do not guess dosage."
            })

        # 4. Missing duration
        if duration is None or duration <= 0:
            alerts.append({
                "type": "missing_duration",
                "severity": "low",
                "medicine_name": name,
                "message": f"'{name}': Treatment duration (number of days) not specified. Confirm course duration with prescriber."
            })

        # 5. Duplicate medicine detection
        simplified_name = name.split()[0] if name else ""
        if simplified_name and len(simplified_name) > 3:
            if simplified_name in seen_names:
                alerts.append({
                    "type": "potential_duplicate",
                    "severity": "high",
                    "medicine_name": name,
                    "message": f"Potential duplicate or overlapping medication detected: '{name}' and '{seen_names[simplified_name]}'. Please verify this information with a doctor or pharmacist."
                })
            else:
                seen_names[simplified_name] = name

    return alerts
