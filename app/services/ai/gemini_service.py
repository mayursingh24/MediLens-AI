import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from flask import current_app
from google import genai
from google.genai import types
from app.utils.logger import get_logger

logger = get_logger()


def get_gemini_client() -> Optional[genai.Client]:
    """Initialize and return a Google GenAI client using the configured API key."""
    api_key = (current_app.config.get("GEMINI_API_KEY") if current_app else None) or os.getenv("GEMINI_API_KEY")
    if not api_key:
        from dotenv import load_dotenv
        from config import BASE_DIR
        load_dotenv(BASE_DIR / ".env", override=True)
        api_key = os.getenv("GEMINI_API_KEY")
        if current_app and api_key:
            current_app.config["GEMINI_API_KEY"] = api_key

    if not api_key:
        logger.warning("GEMINI_API_KEY is not configured.")
        return None
    return genai.Client(api_key=api_key)


def analyze_prescription_images_with_gemini(
    image_paths: List[str],
    ocr_context: str = "",
    model_name: str = "gemini-3.5-flash-lite"
):
    """
    Call Gemini Multimodal Vision API on prescription image(s) with accompanying OCR context.
    Returns the raw string output from Gemini.
    """
    client = get_gemini_client()
    if not client:
        raise ValueError("Google Gemini API key is missing or not configured in environment (GEMINI_API_KEY).")

    system_instruction = (
        "You are an expert medical transcription vision assistant for MediLens AI.\n"
        "Your task is to transcribe handwritten and printed doctor prescriptions into structured JSON with extreme precision.\n\n"
        "CRITICAL MEDICAL SAFETY AND TRANSLATION RULES:\n"
        "1. DO NOT GUESS unclear handwriting or illegible medicine names. If any drug name, dosage, or frequency is unclear, "
        "mark verification_status as 'unclear' or 'review_required' and add a clear note in unclear_items.\n"
        "2. DO NOT hallucinate medications, diagnoses, or treatments.\n"
        "3. Provide output STRICTLY in the specified JSON format and nothing else.\n"
        "4. Standardize prescription notation:\n"
        "   - '1-0-1' or 'BD' / 'BID': morning=1, afternoon=0, evening=0, night=1\n"
        "   - '1-1-1' or 'TDS' / 'TID': morning=1, afternoon=1, evening=0, night=1\n"
        "   - '0-0-1' or 'HS' / 'Bedtime': morning=0, afternoon=0, evening=0, night=1\n"
        "   - '1-0-0' or 'OD' (morning): morning=1, afternoon=0, evening=0, night=0\n"
        "   - 'SOS' or 'PRN': as needed for symptom spikes\n"
        "   ONLY interpret notation when context is sufficiently clear.\n"
        "5. Distinguish food instructions: 'Before food', 'After food', 'With food', 'Empty stomach'.\n"
        "6. Verification status must be one of: 'verified' (crystal clear), 'review_required' (minor ambiguity), or 'unclear' (illegible).\n"
        "7. For EVERY medicine, provide independent confidence scores (0-100) for: medicine, strength, dose, frequency, duration."
    )

    prompt = (
        "Analyze the provided prescription image(s) carefully. "
        "Transcribe all prescription information into this JSON format:\n\n"
        "{\n"
        '  "patient_name": "...",\n'
        '  "doctor_name": "...",\n'
        '  "prescription_date": "YYYY-MM-DD or as written",\n'
        '  "medicines": [\n'
        "    {\n"
        '      "name": "Medicine name as written",\n'
        '      "brand_name": "Brand name if distinct",\n'
        '      "generic_name": "Generic active ingredient",\n'
        '      "strength": "e.g. 500 mg",\n'
        '      "form": "Tablet, Capsule, Syrup, Ointment, etc.",\n'
        '      "dosage": "e.g. 1 tablet",\n'
        '      "frequency": "e.g. 1-0-1, OD, BD, Twice daily",\n'
        '      "morning": 1,\n'
        '      "afternoon": 0,\n'
        '      "evening": 0,\n'
        '      "night": 1,\n'
        '      "duration_days": 5,\n'
        '      "food_instruction": "After food",\n'
        '      "special_instruction": "Take with water",\n'
        '      "quantity": 10,\n'
        '      "confidence": 95,\n'
        '      "confidence_breakdown": {\n'
        '        "medicine": 98,\n'
        '        "strength": 95,\n'
        '        "dose": 92,\n'
        '        "frequency": 94,\n'
        '        "duration": 85\n'
        '      },\n'
        '      "why_taking_this": "This medicine is commonly used to...",\n'
        '      "verification_status": "verified",\n'
        '      "source_page": 1\n'
        "    }\n"
        "  ],\n"
        '  "general_instructions": ["Advice given by doctor, e.g. drink plenty of fluids"],\n'
        '  "unclear_items": ["List of any words, abbreviations, or values that were ambiguous"]\n'
        "}\n\n"
    )

    if ocr_context:
        prompt += f"OCR engine preliminary reading context:\n\"\"\"\n{ocr_context[:2500]}\n\"\"\"\n\n"

    prompt += "Return ONLY the raw JSON object."

    contents: List[Any] = [prompt]

    # Load image parts
    for idx, img_path in enumerate(image_paths, start=1):
        p = Path(img_path)
        if not p.exists():
            continue
        ext = p.suffix.lower()
        mime_type = "image/png" if ext == ".png" else "image/jpeg"
        with open(p, "rb") as f:
            img_bytes = f.read()
        part = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
        contents.append(part)

    models_to_try = [model_name]
    for alt in ["gemini-3.5-flash-lite", "gemini-flash-latest", "gemini-3.8-flash", "gemini-3.1-flash-lite", "gemini-3.5-flash"]:
        if alt not in models_to_try:
            models_to_try.append(alt)

    last_error = None
    for target_model in models_to_try:
        try:
            logger.info(f"Invoking Gemini model '{target_model}' on {len(image_paths)} image(s)...")
            response = client.models.generate_content(
                model=target_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.1,  # Low temperature for factual transcription fidelity
                )
            )
            if response and response.text:
                return response.text
        except Exception as e:
            logger.warning(f"Gemini call with '{target_model}' failed: {e}. Trying fallback if available.")
            last_error = e

    logger.error(f"All Gemini Vision attempts failed. Last error: {last_error}")
    raise RuntimeError(f"Gemini API error: {str(last_error)}")
