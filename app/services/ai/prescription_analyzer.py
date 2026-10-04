from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from flask import current_app
from app.services.pdf.poppler_service import convert_pdf_to_images
from app.services.vision.opencv_service import process_prescription_image
from app.services.ocr.tesseract_service import extract_text_from_image
from app.services.ocr.ocr_validator import validate_ocr_result
from app.services.ai.gemini_service import analyze_prescription_images_with_gemini
from app.utils.json_parser import parse_and_validate_gemini_prescription
from app.services.ai.extraction_validator import cross_validate_prescription
from app.services.ai.safety_engine import run_prescription_safety_checks
from app.services.ai.patient_context import analyze_patient_context_for_medicines
from app.services.medication.medicine_info_service import (
    fetch_general_medicine_info,
    check_drug_drug_interactions,
    detect_duplicate_medications
)
from app.services.pricing.price_service import get_estimated_price
from app.utils.logger import get_logger

logger = get_logger()


def analyze_complete_prescription(
    file_path: str,
    file_type: str,
    user_id: int,
    profile_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Premium AI Prescription Intelligence Pipeline:
    1. Extract page images (Poppler for PDF or single image).
    2. OpenCV quality analysis & adaptive preprocessing on each page.
    3. Tesseract OCR for baseline transcription and bounding boxes.
    4. OCR readability validation.
    5. Gemini Vision multimodal extraction (Medicines, Notation, Instructions).
    6. Strict JSON Parsing with independent confidence breakdown.
    7. Cross-validation between OCR & Gemini transcription.
    8. Patient Context Engine (Pediatric/Adult/Older Adult & Weight/Allergy checks).
    9. Real Medicine Intelligence Retrieval (OpenFDA + DailyMed authoritative sources).
    10. Real Price Intelligence (DPCO/Jan Aushadhi).
    11. Drug-Drug Interaction Intelligence.
    12. Duplicate Therapeutic Class Detection.
    """
    path_obj = Path(file_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Prescription file not found at: {file_path}")

    # Step 1: Obtain Page Images
    page_images: List[Tuple[int, str]] = []
    if file_type == "pdf":
        page_images = convert_pdf_to_images(file_path)
    else:
        page_images = [(1, str(file_path))]

    if not page_images:
        raise ValueError("Could not extract any pages from the uploaded file.")

    # Step 2 & 3: OpenCV Enhancement & Tesseract OCR for each page
    enhanced_image_paths = []
    ocr_texts = []
    total_quality_score = 0
    quality_ratings = []
    all_ocr_metadata = []

    for page_num, img_path in page_images:
        prefix = f"u{user_id}_{path_obj.stem}_p{page_num}"
        cv_result = process_prescription_image(img_path, output_name_prefix=prefix)
        enhanced_image_paths.append(cv_result["enhanced_image_path"])

        quality_report = cv_result["quality_report"]
        total_quality_score += quality_report["score"]
        quality_ratings.append(cv_result["quality_status"])

        # Run OCR on enhanced binary image
        ocr_result = extract_text_from_image(cv_result["ocr_binary_path"], page_number=page_num)
        all_ocr_metadata.append(ocr_result)
        if ocr_result.get("text"):
            ocr_texts.append(f"--- Page {page_num} ---\n" + ocr_result["text"])

    combined_ocr_text = "\n\n".join(ocr_texts).strip()

    # Determine overall OCR quality
    if "poor" in quality_ratings:
        overall_ocr_quality = "poor"
    elif "fair" in quality_ratings:
        overall_ocr_quality = "fair"
    else:
        overall_ocr_quality = "good"

    # Step 4: OCR Readability Validation
    combined_ocr_dict = {
        "text": combined_ocr_text,
        "mean_confidence": total_quality_score / max(1, len(page_images)),
        "word_count": sum(m.get("word_count", 0) for m in all_ocr_metadata),
    }
    is_readable, unreadable_msg = validate_ocr_result(combined_ocr_dict)

    # Step 5: Gemini Multimodal Vision Execution
    try:
        gemini_raw = analyze_prescription_images_with_gemini(
            image_paths=enhanced_image_paths,
            ocr_context=combined_ocr_text,
        )
    except Exception as e:
        logger.error(f"Gemini API failure during prescription analysis: {e}")
        if not is_readable:
            raise ValueError(f"{unreadable_msg} (AI Vision Error: {str(e)})")
        raise RuntimeError(f"AI Vision extraction unavailable: {str(e)}")

    # Step 6: Strict JSON Parsing
    parsed_prescription = parse_and_validate_gemini_prescription(gemini_raw)

    # Step 7: Cross Validation
    cross_validate_prescription(parsed_prescription, combined_ocr_text, overall_ocr_quality)

    extracted_medicines = parsed_prescription.get("medicines", [])
    patient_age_cat = profile_data.get("age_category", "adult") if profile_data else "adult"

    # Step 8: Patient Context Analysis (Pediatric weight, Geriatric, Allergies)
    patient_context_assessment = analyze_patient_context_for_medicines(profile_data, extracted_medicines)

    # Step 9: Authoritative External Medicine Intelligence & Dual-AI Dietary Enrichment (Parallelized)
    def _enrich_single_medicine(med):
        m_name = med.get("name") or ""
        m_strength = med.get("strength") or ""

        # Fetch OpenFDA & DailyMed Verified Intelligence
        try:
            intel = fetch_general_medicine_info(m_name, patient_age_category=patient_age_cat)
            med["external_intelligence"] = intel
            if intel.get("status") == "success":
                if intel.get("brand_name"):
                    med["brand_name"] = str(intel["brand_name"])[:255]
                if intel.get("generic_name"):
                    med["generic_name"] = str(intel["generic_name"])[:500]
                if intel.get("why_taking_this"):
                    med["why_taking_this"] = intel["why_taking_this"]
        except Exception as e:
            logger.warning(f"Failed external intelligence lookup for {m_name}: {e}")
            med["external_intelligence"] = None

        # Fetch Dual-AI Dietary & Lifestyle Precautions (Kya khayein aur kya na khayein)
        try:
            from app.services.ai.groq_service import generate_dietary_precautions_dual_ai
            diet_info = generate_dietary_precautions_dual_ai(
                medicine_name=m_name,
                generic_name=med.get("generic_name"),
                dosage=med.get("dosage"),
                frequency=med.get("frequency")
            )
            med["dietary_guidelines"] = diet_info
        except Exception as e:
            logger.warning(f"Dietary precautions failed for {m_name}: {e}")
            med["dietary_guidelines"] = None

        # Fetch Real Generic Pricing
        try:
            price_info = get_estimated_price(m_name, m_strength)
            med["estimated_price"] = price_info
        except Exception:
            med["estimated_price"] = None

    if extracted_medicines:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(extracted_medicines))) as executor:
            list(executor.map(_enrich_single_medicine, extracted_medicines))

    # Step 10: Drug-Drug Interaction Checking
    interactions = check_drug_drug_interactions(extracted_medicines)

    # Step 11: Duplicate Therapeutic Class Detection
    duplicates = detect_duplicate_medications(extracted_medicines)

    # Step 12: Baseline Safety Checks
    safety_alerts = run_prescription_safety_checks(extracted_medicines)

    clinical_safety_summary = {
        "patient_context": patient_context_assessment,
        "interactions": interactions,
        "duplicates": duplicates,
        "general_safety_alerts": safety_alerts
    }

    return {
        "page_count": len(page_images),
        "ocr_quality": overall_ocr_quality,
        "raw_ocr_text": combined_ocr_text,
        "gemini_raw_response": gemini_raw,
        "structured_data": parsed_prescription,
        "clinical_safety": clinical_safety_summary,
        "enhanced_images": enhanced_image_paths,
    }
