import os
from pathlib import Path
from typing import List, Tuple
from pdf2image import convert_from_path
from flask import current_app
from app.utils.logger import get_logger

logger = get_logger()


def get_configured_poppler_path() -> str:
    """Find and return poppler binary path."""
    configured = current_app.config.get("POPPLER_PATH")
    if configured and os.path.exists(configured):
        return configured

    # Common Windows fallbacks
    common_paths = [
        r"C:\poppler\poppler-26.02.0\Library\bin",
        r"C:\poppler\Library\bin",
        r"C:\Program Files\poppler\bin",
        r"C:\Program Files\poppler\Library\bin",
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p
    return ""


def convert_pdf_to_images(pdf_path: str, output_folder: str = None) -> List[Tuple[int, str]]:
    """
    Convert a PDF file into individual page images.
    Returns a list of tuples: (page_number, image_path).
    """
    path_obj = Path(pdf_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

    target_folder = Path(output_folder or current_app.config["PROCESSED_FOLDER"])
    target_folder.mkdir(parents=True, exist_ok=True)

    poppler_bin = get_configured_poppler_path()
    logger.info(f"Converting PDF '{path_obj.name}' to images using Poppler: '{poppler_bin or 'system PATH'}'")

    try:
        kwargs = {"dpi": 200, "fmt": "jpeg"}
        if poppler_bin:
            kwargs["poppler_path"] = poppler_bin

        images = convert_from_path(str(path_obj), **kwargs)
        page_results = []

        base_stem = path_obj.stem
        for idx, img in enumerate(images, start=1):
            out_filename = f"{base_stem}_page_{idx}.jpg"
            out_path = target_folder / out_filename
            img.save(str(out_path), "JPEG", quality=92)
            page_results.append((idx, str(out_path)))

        logger.info(f"Successfully converted PDF into {len(page_results)} page image(s).")
        return page_results

    except Exception as e:
        logger.error(f"Error converting PDF {pdf_path} with poppler: {e}")
        raise RuntimeError(f"PDF processing failed: {str(e)}")
