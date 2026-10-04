import os
from pathlib import Path
from typing import Dict, Any, List
from PIL import Image
import pytesseract
from pytesseract import Output
from flask import current_app
from app.utils.logger import get_logger

logger = get_logger()


def configure_tesseract():
    """Ensure pytesseract has the proper binary path set."""
    configured = current_app.config.get("TESSERACT_CMD")
    if configured and os.path.exists(configured):
        pytesseract.pytesseract.tesseract_cmd = configured
        return

    # Check common Windows paths
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            pytesseract.pytesseract.tesseract_cmd = c
            return


def extract_text_from_image(image_path: str, page_number: int = 1) -> Dict[str, Any]:
    """
    Extract OCR text, bounding boxes, word confidences, and page number from an image.
    """
    configure_tesseract()
    path_obj = Path(image_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Image not found for OCR: {image_path}")

    try:
        with Image.open(str(path_obj)) as pil_img:
            data = pytesseract.image_to_data(pil_img, output_type=Output.DICT)

        words = []
        confidences = []
        boxes = []
        full_text_pieces = []

        n_boxes = len(data["text"])
        for i in range(n_boxes):
            word = data["text"][i].strip()
            conf = int(data["conf"][i])
            if word:
                full_text_pieces.append(word)
                if conf > 0:
                    confidences.append(conf)
                    boxes.append({
                        "text": word,
                        "confidence": conf,
                        "x": data["left"][i],
                        "y": data["top"][i],
                        "w": data["width"][i],
                        "h": data["height"][i],
                        "page": page_number
                    })

        raw_text = " ".join(full_text_pieces).strip()
        mean_confidence = float(sum(confidences) / len(confidences)) if confidences else 0.0

        return {
            "text": raw_text,
            "mean_confidence": round(mean_confidence, 2),
            "word_count": len(full_text_pieces),
            "boxes": boxes,
            "page_number": page_number,
        }

    except Exception as e:
        logger.error(f"Tesseract OCR execution failed for {image_path}: {e}")
        return {
            "text": "",
            "mean_confidence": 0.0,
            "word_count": 0,
            "boxes": [],
            "page_number": page_number,
            "error": str(e)
        }
