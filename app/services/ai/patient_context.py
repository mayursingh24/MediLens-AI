from typing import Dict, Any, List, Optional
from app.utils.logger import get_logger

logger = get_logger()


def analyze_patient_context_for_medicines(
    profile_data: Optional[Dict[str, Any]],
    medicines: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Patient Context Engine:
    Evaluates patient demographics, weight, age, and allergies against prescribed medications.
    Enforces clinical safety:
    - Distinguishes Pediatric (< 18), Adult (18-64), Older Adult (65+).
    - Pediatric checks: Identifies weight-based dosing necessity. If weight is missing,
      flags 'Additional information required' without inventing doses.
    - Older adult checks: Highlights renal / fall / sedation cautions.
    - Allergy checks: Cross-references patient allergy records against medicine names/classes.
    """
    if not profile_data:
        profile_data = {
            "name": "Patient",
            "age": None,
            "weight_kg": None,
            "gender": None,
            "allergies": [],
            "existing_conditions": [],
            "pregnancy_status": None,
            "age_category": "adult"
        }

    age = profile_data.get("age")
    weight_kg = profile_data.get("weight_kg")
    allergies = [a.lower().strip() for a in profile_data.get("allergies", []) if a]
    existing_conditions = [c.lower().strip() for c in profile_data.get("existing_conditions", []) if c]
    pregnancy = str(profile_data.get("pregnancy_status") or "").lower()

    # Determine age category
    if age is not None:
        if age < 18:
            age_category = "pediatric"
        elif age >= 65:
            age_category = "older_adult"
        else:
            age_category = "adult"
    else:
        age_category = "adult"

    clinical_alerts: List[Dict[str, Any]] = []
    medicine_context_evaluations: List[Dict[str, Any]] = []

    # Common weight-sensitive pediatric drug classes / generics
    weight_sensitive_keywords = [
        "amoxicillin", "azithromycin", "cefixime", "paracetamol", "ibuprofen",
        "augmentin", "syrup", "suspension", "drops", "pediatric"
    ]

    for med in medicines:
        m_name = (med.get("display_name") or med.get("name") or "").lower()
        strength = (med.get("display_strength") or med.get("strength") or "")
        form = (med.get("display_form") or med.get("form") or "").lower()
        m_eval = {
            "medicine_name": med.get("display_name") or med.get("name"),
            "age_category": age_category,
            "weight_considered": bool(weight_kg),
            "alerts": []
        }

        # 1. Pediatric Evaluation (< 18 years)
        if age_category == "pediatric":
            is_suspension = any(w in form for w in ["syrup", "suspension", "drop"])
            is_weight_sensitive = any(w in m_name for w in weight_sensitive_keywords) or is_suspension

            if is_weight_sensitive:
                if not weight_kg:
                    alert_msg = (
                        f"Additional information required: '{med.get('display_name') or med.get('name')}' "
                        f"in pediatric patients typically requires weight-based (mg/kg) dosing confirmation. "
                        f"Please enter patient weight in Profile or verify the exact volume with the prescribing clinician."
                    )
                    clinical_alerts.append({
                        "title": f"Pediatric Weight Verification: {med.get('display_name') or med.get('name')}",
                        "type": "pediatric_weight_missing",
                        "category": "Pediatric Dosing",
                        "severity": "high",
                        "medicine": med.get("display_name") or med.get("name"),
                        "message": alert_msg,
                        "action_required": "Confirm patient weight (kg) to compute safe volume."
                    })
                    m_eval["alerts"].append(alert_msg)
                else:
                    m_eval["pediatric_note"] = f"Pediatric patient weight documented ({weight_kg} kg). Dosing should match doctor's written instruction."

            # Minimum age restriction checks (e.g., Fluoroquinolones like Levofloxacin/Ciprofloxacin in young children)
            if any(q in m_name for q in ["levofloxacin", "ciprofloxacin", "ofloxacin"]):
                if age is not None and age < 16:
                    warn = (
                        f"Pediatric Clinical Alert: '{med.get('display_name') or med.get('name')}' belongs to fluoroquinolone class. "
                        f"Typically reserved for specific pediatric indications due to musculoskeletal considerations. Verify with pediatrician."
                    )
                    clinical_alerts.append({
                        "title": f"Pediatric Age Restriction: {med.get('display_name') or med.get('name')}",
                        "type": "pediatric_age_restriction",
                        "category": "Age Restriction",
                        "severity": "high",
                        "medicine": med.get("display_name") or med.get("name"),
                        "message": warn,
                        "action_required": "Verify alternative pediatric antibiotic with clinician."
                    })
                    m_eval["alerts"].append(warn)

        # 2. Older Adult Evaluation (65+ years)
        elif age_category == "older_adult":
            # Sedative / Antihistamines / Anticholinergics (Beers list awareness)
            if any(s in m_name for s in ["ebast", "cetirizine", "hydroxyzine", "diphenhydramine", "diazepam", "alprazolam"]):
                warn = (
                    f"Older Adult Consideration: '{med.get('display_name') or med.get('name')}' has sedative or anticholinergic properties. "
                    f"Monitor for drowsiness, dizziness, or fall risk."
                )
                clinical_alerts.append({
                    "title": f"Sedation / Fall Risk Alert: {med.get('display_name') or med.get('name')}",
                    "type": "older_adult_caution",
                    "category": "Geriatric Caution",
                    "severity": "medium",
                    "medicine": med.get("display_name") or med.get("name"),
                    "message": warn,
                    "action_required": "Take bedtime dose and avoid driving or unassisted night mobility."
                })
                m_eval["alerts"].append(warn)

            # NSAID caution in elderly
            if any(s in m_name for s in ["ibuprofen", "diclofenac", "naproxen", "aceclofenac"]):
                warn = (
                    f"Renal & Gastrointestinal Advisory: Older adults taking NSAIDs like '{med.get('display_name') or med.get('name')}' "
                    f"should monitor blood pressure, renal function, and take with meals to protect stomach lining."
                )
                clinical_alerts.append({
                    "title": f"Renal & GI Advisory: {med.get('display_name') or med.get('name')}",
                    "type": "older_adult_nsaid",
                    "category": "Organ Safety",
                    "severity": "medium",
                    "medicine": med.get("display_name") or med.get("name"),
                    "message": warn,
                    "action_required": "Always consume after full meal; monitor hydration and renal parameters."
                })
                m_eval["alerts"].append(warn)

        # 3. Documented Patient Allergies Cross-Check
        for allergy in allergies:
            if allergy and (allergy in m_name or m_name in allergy):
                alert_msg = (
                    f"CRITICAL ALLERGY MATCH: Patient has documented allergy to '{allergy.capitalize()}', "
                    f"which matches prescribed medicine '{med.get('display_name') or med.get('name')}'. "
                    f"Do not administer without immediate prescriber confirmation."
                )
                clinical_alerts.append({
                    "title": f"Documented Allergy Conflict: {allergy.capitalize()}",
                    "type": "allergy_conflict",
                    "category": "Allergy Alert",
                    "severity": "critical",
                    "medicine": med.get("display_name") or med.get("name"),
                    "message": alert_msg,
                    "action_required": "Do NOT take without doctor/pharmacist providing safe alternative."
                })
                m_eval["alerts"].append(alert_msg)

        # 4. Pregnancy Considerations
        if pregnancy in {"positive", "yes", "true", "pregnant"}:
            if any(t in m_name for t in ["doxycycline", "methotrexate", "atorvastatin", "warfarin", "retinoid"]):
                alert_msg = (
                    f"PREGNANCY CAUTION: '{med.get('display_name') or med.get('name')}' carries significant clinical contraindications "
                    f"during pregnancy. Confirm treatment alternative immediately with obstetrician/prescriber."
                )
                clinical_alerts.append({
                    "title": f"Pregnancy Contraindication: {med.get('display_name') or med.get('name')}",
                    "type": "pregnancy_contraindication",
                    "category": "Teratogenic / Pregnancy Risk",
                    "severity": "critical",
                    "medicine": med.get("display_name") or med.get("name"),
                    "message": alert_msg,
                    "action_required": "Consult gynecologist / prescribing doctor immediately before use."
                })
                m_eval["alerts"].append(alert_msg)

        medicine_context_evaluations.append(m_eval)

    return {
        "age_category": age_category,
        "age": age,
        "weight_kg": weight_kg,
        "allergies": profile_data.get("allergies", []),
        "clinical_alerts": clinical_alerts,
        "medicine_evaluations": medicine_context_evaluations,
    }
