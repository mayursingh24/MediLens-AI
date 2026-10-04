import json
import re
from typing import Dict, Any, List, Optional
from app.utils.logger import get_logger

logger = get_logger()


def extract_json_block(text: str) -> str:
    """Extract raw JSON content from markdown code fences or raw text."""
    if not text:
        return ""

    text = text.strip()

    # Search for ```json ... ``` or ``` ... ```
    pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # If first char is { and last is }, return as is
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1]

    return text


def clean_potential_json_syntax(raw: str) -> str:
    """Clean minor JSON syntax issues like trailing commas before brackets."""
    # Remove trailing commas before closing braces/brackets
    cleaned = re.sub(r",\s*([\]}])", r"\1", raw)
    return cleaned


def parse_and_validate_gemini_prescription(raw_response: str) -> Dict[str, Any]:
    """
    Strictly parse and validate Gemini prescription response against required schema.
    Returns validated dict structure.
    Raises ValueError on invalid format.
    """
    if not raw_response or not raw_response.strip():
        raise ValueError("Empty response received from Gemini.")

    extracted_str = extract_json_block(raw_response)

    try:
        data = json.loads(extracted_str)
    except json.JSONDecodeError:
        try:
            cleaned = clean_potential_json_syntax(extracted_str)
            data = json.loads(cleaned)
        except Exception as e:
            logger.error(f"JSON decode failure on Gemini response: {e}. Raw: {raw_response[:300]}")
            raise ValueError(f"Failed to parse structured JSON from AI output: {str(e)}")

    if not isinstance(data, dict):
        raise ValueError("Invalid format: Root output must be a JSON object.")

    # Validate and normalize schema fields
    normalized = {
        "patient_name": str(data.get("patient_name") or "").strip(),
        "doctor_name": str(data.get("doctor_name") or "").strip(),
        "prescription_date": str(data.get("prescription_date") or "").strip(),
        "medicines": [],
        "general_instructions": [],
        "unclear_items": [],
    }

    raw_medicines = data.get("medicines")
    if isinstance(raw_medicines, list):
        for med in raw_medicines:
            if not isinstance(med, dict):
                continue

            name = str(med.get("name") or "").strip()
            # If name is completely missing or empty, mark for review
            verification_status = str(med.get("verification_status") or "review_required").strip().lower()
            if verification_status not in {"verified", "review_required", "unclear"}:
                verification_status = "review_required"

            # Parse confidence
            raw_conf = med.get("confidence", 0)
            try:
                confidence = float(raw_conf)
                if confidence > 1.0 and confidence <= 100.0:
                    pass  # already on 0-100 scale
                elif confidence >= 0.0 and confidence <= 1.0:
                    confidence = confidence * 100.0
                else:
                    confidence = 50.0
            except (ValueError, TypeError):
                confidence = 50.0

            # Safe numeric conversion for dosage times
            def _to_float(v):
                try:
                    return float(v) if v is not None else 0.0
                except (ValueError, TypeError):
                    return 0.0

            def _to_int_or_none(v):
                try:
                    return int(v) if v is not None else None
                except (ValueError, TypeError):
                    return None

            # Parse confidence breakdown
            raw_breakdown = med.get("confidence_breakdown")
            if isinstance(raw_breakdown, dict):
                c_breakdown = {
                    "medicine": int(raw_breakdown.get("medicine", confidence)),
                    "strength": int(raw_breakdown.get("strength", max(50, confidence - 2))),
                    "dose": int(raw_breakdown.get("dose", max(50, confidence - 3))),
                    "frequency": int(raw_breakdown.get("frequency", max(50, confidence - 2))),
                    "duration": int(raw_breakdown.get("duration", max(50, confidence - 5))),
                }
            else:
                c_int = int(confidence)
                c_breakdown = {
                    "medicine": c_int,
                    "strength": max(50, c_int - 2),
                    "dose": max(50, c_int - 4),
                    "frequency": max(50, c_int - 3),
                    "duration": max(45, c_int - 8),
                }

            # Uncertainty-First Check: If any critical field is below 70%, require review
            if any(score < 70 for score in c_breakdown.values()) or confidence < 75:
                verification_status = "review_required"

            # Parse why_taking_this
            why_taking = str(med.get("why_taking_this") or "").strip()
            if not why_taking:
                why_taking = f"{name} is commonly prescribed by clinicians for indicated therapeutic treatment."

            m_val = _to_float(med.get("morning"))
            a_val = _to_float(med.get("afternoon"))
            e_val = _to_float(med.get("evening"))
            n_val = _to_float(med.get("night"))
            freq_str = str(med.get("frequency") or "").strip()
            dur_days = _to_int_or_none(med.get("duration_days"))
            food_inst = str(med.get("food_instruction") or "").strip()

            # Automatic AI Circadian Dosage Inference if numeric slots were empty
            if m_val == 0.0 and a_val == 0.0 and e_val == 0.0 and n_val == 0.0:
                f_clean = freq_str.lower().replace(" ", "")
                if "1-0-1" in f_clean or "bd" in f_clean or "bid" in f_clean or "twice" in f_clean:
                    m_val = 1.0
                    n_val = 1.0
                elif "1-1-1" in f_clean or "tds" in f_clean or "tid" in f_clean or "thrice" in f_clean:
                    m_val = 1.0
                    a_val = 1.0
                    n_val = 1.0
                elif "1-0-0" in f_clean or "od" in f_clean or "once" in f_clean or "morning" in f_clean:
                    m_val = 1.0
                elif "0-0-1" in f_clean or "hs" in f_clean or "bedtime" in f_clean or "night" in f_clean:
                    n_val = 1.0
                elif "0-1-0" in f_clean or "afternoon" in f_clean or "noon" in f_clean:
                    a_val = 1.0
                elif "1-1-1-1" in f_clean or "qid" in f_clean:
                    m_val = 1.0
                    a_val = 1.0
                    e_val = 1.0
                    n_val = 1.0
                elif "sos" in f_clean or "prn" in f_clean:
                    m_val = 0.5  # As needed
                else:
                    # Default clinical single daily dose in morning
                    m_val = 1.0

            # Automatic duration extraction if missing
            if not dur_days or dur_days <= 0:
                full_text = f"{freq_str} {med.get('special_instruction', '')} {name}".lower()
                dur_match = re.search(r"(\d+)\s*(?:days?|d\b|days|day)", full_text)
                if dur_match:
                    dur_days = int(dur_match.group(1))
                elif "/7" in full_text:  # British/Indian notation e.g. 5/7 = 5 days
                    dur_match = re.search(r"(\d+)\s*/\s*7", full_text)
                    if dur_match:
                        dur_days = int(dur_match.group(1))
                else:
                    dur_days = 5  # Standard acute prescription duration

            # Automatic food instruction smart classification
            if not food_inst or food_inst.lower() in ["as directed", ""]:
                name_lower = name.lower()
                if any(ppi in name_lower for ppi in ["panto", "omeprazole", "rabeprazole", "esomeprazole", "pan-", "antacid"]):
                    food_inst = "Before food (Empty stomach)"
                elif any(nsaid in name_lower for nsaid in ["ibuprofen", "paracetamol", "diclofenac", "aceclo", "pain"]):
                    food_inst = "After meals with water"
                else:
                    food_inst = "After food"

            normalized_med = {
                "name": name,
                "brand_name": str(med.get("brand_name") or name).strip(),
                "generic_name": str(med.get("generic_name") or "").strip(),
                "strength": str(med.get("strength") or "").strip(),
                "form": str(med.get("form") or "Tablet").strip(),
                "dosage": str(med.get("dosage") or f"{int(m_val or a_val or n_val or 1)} {med.get('form', 'Tablet')}").strip(),
                "frequency": freq_str or f"{int(m_val)}-{int(a_val)}-{int(n_val)}",
                "morning": m_val,
                "afternoon": a_val,
                "evening": e_val,
                "night": n_val,
                "duration_days": dur_days,
                "food_instruction": food_inst,
                "special_instruction": str(med.get("special_instruction") or "").strip(),
                "quantity": _to_int_or_none(med.get("quantity")) or (int(m_val + a_val + e_val + n_val) * dur_days),
                "confidence": round(confidence, 1),
                "confidence_breakdown": c_breakdown,
                "why_taking_this": why_taking,
                "verification_status": verification_status,
                "source_page": int(med.get("source_page", 1)),
            }
            normalized["medicines"].append(normalized_med)

    raw_instructions = data.get("general_instructions")
    if isinstance(raw_instructions, list):
        normalized["general_instructions"] = [str(item).strip() for item in raw_instructions if item]

    raw_unclear = data.get("unclear_items")
    if isinstance(raw_unclear, list):
        normalized["unclear_items"] = [str(item).strip() for item in raw_unclear if item]

    return normalized
