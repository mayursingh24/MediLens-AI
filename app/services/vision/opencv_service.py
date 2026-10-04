import cv2
from pathlib import Path
from typing import Dict, Any
from flask import current_app
from app.services.vision.image_quality import analyze_image_quality
from app.services.vision.preprocessing import preprocess_adaptively
from app.utils.logger import get_logger

logger = get_logger()


def process_prescription_image(image_path: str, output_name_prefix: str = "enhanced") -> Dict[str, Any]:
    """
    Complete OpenCV enhancement pipeline for a prescription image:
    1. Loads image.
    2. Runs quality analysis (blur, brightness, contrast, resolution).
    3. Runs adaptive preprocessing (deskew, contrast, noise reduction, threshold).
    4. Saves processed artifacts for OCR and Gemini Vision.
    """
    path_obj = Path(image_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    img = cv2.imread(str(path_obj))
    if img is None:
        raise ValueError(f"Could not decode image at {image_path}")

    # Analyze quality
    quality_report = analyze_image_quality(img)
    logger.info(
        f"Image Quality for {path_obj.name}: rating={quality_report['quality']}, "
        f"blur_score={quality_report['blur_score']}, brightness={quality_report['brightness']}, "
        f"contrast={quality_report['contrast']}"
    )

    # Adaptively preprocess
    enhanced_color, ocr_binary = preprocess_adaptively(img, quality_report)

    # Save processed versions
    processed_dir = Path(current_app.config["PROCESSED_FOLDER"])
    processed_dir.mkdir(parents=True, exist_ok=True)

    enhanced_path = processed_dir / f"{output_name_prefix}_enhanced.jpg"
    ocr_binary_path = processed_dir / f"{output_name_prefix}_ocr.png"

    cv2.imwrite(str(enhanced_path), enhanced_color, [cv2.IMWRITE_JPEG_QUALITY, 95])
    cv2.imwrite(str(ocr_binary_path), ocr_binary)

    return {
        "quality_report": quality_report,
        "quality_status": quality_report["quality"],
        "original_path": str(path_obj),
        "enhanced_image_path": str(enhanced_path),
        "ocr_binary_path": str(ocr_binary_path),
    }
