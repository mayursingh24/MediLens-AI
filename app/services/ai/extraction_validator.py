import difflib
import re
from typing import Dict, Any, List, Tuple


def calculate_similarity(a: str, b: str) -> float:
    """Calculate string similarity ratio between 0.0 and 1.0."""
    if not a or not b:
        return 0.0
    a_norm = re.sub(r"[^a-zA-Z0-9]", "", a.lower())
    b_norm = re.sub(r"[^a-zA-Z0-9]", "", b.lower())
    if not a_norm or not b_norm:
        return 0.0
    return difflib.SequenceMatcher(None, a_norm, b_norm).ratio()


def find_best_ocr_match(target_text: str, ocr_text: str) -> Tuple[str, float]:
    """Find the snippet in raw OCR text that most closely matches the target medicine or strength."""
    if not target_text or not ocr_text:
        return "", 0.0

    target_words = target_text.strip().split()
    ocr_words = ocr_text.strip().split()

    if not ocr_words:
        return "", 0.0

    window_size = max(1, len(target_words))
    best_match_phrase = ""
    best_score = 0.0

    # Slide window over OCR tokens
    for i in range(len(ocr_words) - window_size + 1):
        window = " ".join(ocr_words[i : i + window_size])
        sim = calculate_similarity(target_text, window)
        if sim > best_score:
            best_score = sim
            best_match_phrase = window

    # Also test single words if window size > 1
    if len(target_words) > 1:
        first_word = target_words[0]
        for w in ocr_words:
            sim = calculate_similarity(first_word, w)
            if sim * 0.9 > best_score:
                best_score = sim * 0.9
                best_match_phrase = w

    return best_match_phrase, best_score


def cross_validate_medicine(
    medicine: Dict[str, Any],
    raw_ocr_text: str,
    ocr_quality: str = "fair"
) -> Dict[str, Any]:
    """
    Cross-validate Gemini extracted medicine against Tesseract raw OCR text.
    Assesses name, strength, dosage, and assigns explainable analysis & verification status.
    """
    med_name = (medicine.get("name") or "").strip()
    strength = (medicine.get("strength") or "").strip()
    dosage = (medicine.get("dosage") or "").strip()
    original_conf = float(medicine.get("confidence", 50.0))

    # Search for medicine name in OCR text
    matched_ocr_snippet, match_score = find_best_ocr_match(med_name, raw_ocr_text)

    # Search for strength numbers (e.g. 500, 250, 10) in OCR text
    strength_confirmed = False
    strength_numbers = re.findall(r"\d+", strength)
    if strength_numbers:
        for num in strength_numbers:
            if re.search(rf"\b{num}(?:\s*(?:mg|mcg|g|ml))?", raw_ocr_text, re.IGNORECASE) or num in raw_ocr_text:
                strength_confirmed = True
                break
    else:
        strength_confirmed = True  # No numeric strength required

    # Determine validation status and explainable AI messages
    conflict_notes = []
    final_status = "review_required"
    calculated_confidence = original_conf

    # Check for unclear handwriting triggers
    name_is_vague = not med_name or med_name.lower() in {"unclear", "unknown", "illegible", "medicine"}
    if name_is_vague or medicine.get("verification_status") == "unclear":
        final_status = "unclear"
        calculated_confidence = min(calculated_confidence, 35.0)
        conflict_notes.append(
            "⚠️ Medicine Name Unclear: The prescription handwriting could not be transcribed confidently. "
            "Please verify this information with your doctor or pharmacist."
        )
    elif match_score >= 0.80:
        # High confidence match between Gemini and OCR
        if strength_confirmed and original_conf >= 80.0:
            final_status = "verified"
            calculated_confidence = max(original_conf, 90.0)
            conflict_notes.append(
                f"High confidence match: AI extracted '{med_name}' and OCR detected '{matched_ocr_snippet}' (Similarity {int(match_score*100)}%)."
            )
        else:
            final_status = "review_required"
            calculated_confidence = max(original_conf, 75.0)
            conflict_notes.append(
                f"Moderate match ({int(match_score*100)}%): Name corresponds with OCR ('{matched_ocr_snippet}'), but strength/dosage requires confirmation."
            )
    elif match_score >= 0.50:
        # Partial match
        final_status = "review_required"
        calculated_confidence = min(original_conf, 70.0)
        conflict_notes.append(
            f"⚠️ Partial match ({int(match_score*100)}%): OCR snippet '{matched_ocr_snippet}' differs from '{med_name}'. Verification recommended."
        )
    else:
        # Low match or OCR could not find the text
        if ocr_quality == "poor":
            final_status = "review_required"
            calculated_confidence = min(original_conf, 65.0)
            conflict_notes.append(
                "OCR quality was poor; identified primarily via Gemini Multimodal Vision. Please review and confirm."
            )
        else:
            final_status = "review_required"
            calculated_confidence = min(original_conf, 60.0)
            conflict_notes.append(
                "⚠️ Verification Required: OCR and AI vision produced different results or OCR text was absent. Never assume accuracy without confirmation."
            )

    medicine["confidence"] = round(calculated_confidence, 1)
    medicine["verification_status"] = final_status
    medicine["ocr_extracted_text"] = matched_ocr_snippet or "Not clearly located in OCR output"
    medicine["gemini_extracted_text"] = f"{med_name} {strength}".strip()
    medicine["conflict_details"] = " | ".join(conflict_notes)

    return medicine


def cross_validate_prescription(prescription_data: Dict[str, Any], raw_ocr_text: str, ocr_quality: str) -> Dict[str, Any]:
    """Validate all medicines in prescription against raw OCR and update overall prescription flags."""
    medicines = prescription_data.get("medicines", [])
    has_unclear = False

    for med in medicines:
        cross_validate_medicine(med, raw_ocr_text, ocr_quality)
        if med["verification_status"] in {"review_required", "unclear"}:
            has_unclear = True

    prescription_data["has_unclear_fields"] = has_unclear
    return prescription_data
