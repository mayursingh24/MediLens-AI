import re
from typing import Dict, Any, Tuple


PRESCRIPTION_UNREADABLE_MESSAGE = "Prescription text could not be read clearly. Please upload a clearer image."


def validate_ocr_result(ocr_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate whether the OCR output contains sufficient readable text to proceed.
    Returns: (is_readable, message_if_unreadable)
    """
    text = (ocr_data.get("text") or "").strip()
    mean_conf = ocr_data.get("mean_confidence", 0.0)
    word_count = ocr_data.get("word_count", 0)

    # Clean punctuation and whitespace
    alphanumeric_chars = re.findall(r"[a-zA-Z0-9]", text)

    if not text or len(alphanumeric_chars) < 5 or word_count < 2:
        return False, PRESCRIPTION_UNREADABLE_MESSAGE

    if mean_conf < 20.0 and len(alphanumeric_chars) < 15:
        return False, PRESCRIPTION_UNREADABLE_MESSAGE

    return True, ""
