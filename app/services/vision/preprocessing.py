import cv2
import numpy as np
from typing import Tuple, Dict, Any


def resize_image_proportional(img: np.ndarray, target_width: int = 1800) -> np.ndarray:
    """Resize image preserving aspect ratio if larger or smaller than optimal OCR size."""
    h, w = img.shape[:2]
    if w == target_width or w < 600:
        return img
    scale = target_width / float(w)
    new_h = int(h * scale)
    return cv2.resize(img, (target_width, new_h), interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC)


def deskew_image(img: np.ndarray) -> np.ndarray:
    """Detect skew angle of text lines and rotate to straighten."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()

    # Invert and threshold to isolate dark text on light background
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]

    # Find coordinates of all non-zero pixels
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 100:
        return img

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    elif angle > 45:
        angle = 90 - angle
    else:
        angle = -angle

    # Only deskew if skew is between 0.5 and 20 degrees
    if abs(angle) < 0.5 or abs(angle) > 20.0:
        return img

    (h, w) = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return rotated


def apply_clahe(gray: np.ndarray, clip_limit: float = 2.0, grid_size: Tuple[int, int] = (8, 8)) -> np.ndarray:
    """Enhance local contrast using Contrast Limited Adaptive Histogram Equalization."""
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=grid_size)
    return clahe.apply(gray)


def sharpen_image(gray: np.ndarray) -> np.ndarray:
    """Sharpen slightly blurred text using unsharp masking."""
    gaussian = cv2.GaussianBlur(gray, (0, 0), 2.0)
    sharpened = cv2.addWeighted(gray, 1.5, gaussian, -0.5, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def adaptive_denoise(img: np.ndarray) -> np.ndarray:
    """Denoise while preserving high-contrast text edges."""
    if len(img.shape) == 3:
        return cv2.fastNlMeansDenoisingColored(img, None, 8, 8, 7, 21)
    return cv2.fastNlMeansDenoising(img, None, 10, 7, 21)


def correct_perspective_if_present(img: np.ndarray) -> np.ndarray:
    """Detect prescription document boundary contour and rectify perspective if clear."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 200)

    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    target_contour = None
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4 and cv2.contourArea(c) > (img.shape[0] * img.shape[1] * 0.35):
            target_contour = approx
            break

    if target_contour is None:
        return img

    # 4 points perspective transform
    pts = target_contour.reshape(4, 2)
    rect = np.zeros((4, 2), dtype="float32")

    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    (tl, tr, br, bl) = rect
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(img, M, (maxWidth, maxHeight))
    return warped


def preprocess_adaptively(img: np.ndarray, quality_report: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    """
    Adaptively preprocess the image according to image quality report.
    Returns: (preprocessed_color_img, preprocessed_gray_or_binary_for_ocr)
    """
    recs = quality_report.get("recommendations", {})
    working_img = img.copy()

    # 1. Perspective check (if needed)
    working_img = correct_perspective_if_present(working_img)

    # 2. Deskew
    working_img = deskew_image(working_img)

    # 3. Resize if needed
    if recs.get("needs_resize", False):
        working_img = resize_image_proportional(working_img, recs.get("target_width", 1800))

    # Convert to grayscale for OCR branch
    gray = cv2.cvtColor(working_img, cv2.COLOR_BGR2GRAY) if len(working_img.shape) == 3 else working_img.copy()

    # 4. Adaptive Denoising
    if recs.get("needs_denoise", False):
        gray = adaptive_denoise(gray)

    # 5. Local Contrast Boost (CLAHE)
    if recs.get("needs_contrast_boost", False):
        gray = apply_clahe(gray, clip_limit=2.5)

    # 6. Sharpening if mildly blurred
    if recs.get("needs_sharpen", False):
        gray = sharpen_image(gray)

    # 7. Adaptive Thresholding to yield clean black-on-white text for OCR engine
    ocr_binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 11
    )

    return working_img, ocr_binary
