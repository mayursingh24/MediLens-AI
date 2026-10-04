import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any


def analyze_image_quality(image_input) -> Dict[str, Any]:
    """
    Analyze image quality to calculate blur, brightness, contrast, resolution,
    and determine overall readability tier ('good', 'fair', 'poor').
    """
    if isinstance(image_input, (str, Path)):
        img = cv2.imread(str(image_input))
        if img is None:
            raise ValueError(f"Unable to read image at {image_input}")
    elif isinstance(image_input, np.ndarray):
        img = image_input
    else:
        raise ValueError("Invalid image input type.")

    h, w = img.shape[:2]
    resolution = w * h

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

    # 1. Blur Detection via Laplacian Variance
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    blur_score = float(laplacian.var())

    # 2. Brightness (Mean grayscale intensity: 0 to 255)
    brightness = float(np.mean(gray))

    # 3. Contrast (Standard deviation of intensity)
    contrast = float(np.std(gray))

    # 4. Aspect Ratio & Resolution check
    is_low_res = (w < 800 or h < 800)
    is_very_blurry = blur_score < 40.0
    is_moderately_blurry = blur_score < 100.0
    is_poor_lighting = (brightness < 60.0 or brightness > 225.0)
    is_low_contrast = contrast < 30.0

    # Determine Quality Tier
    score = 100
    if is_very_blurry:
        score -= 40
    elif is_moderately_blurry:
        score -= 20

    if is_poor_lighting:
        score -= 25

    if is_low_contrast:
        score -= 20

    if is_low_res:
        score -= 15

    if score >= 75 and not is_very_blurry and not is_poor_lighting:
        quality_label = "good"
    elif score >= 45 and not is_very_blurry:
        quality_label = "fair"
    else:
        quality_label = "poor"

    # Preprocessing recommendations for adaptive pipeline
    recommendations = {
        "needs_resize": is_low_res or (w > 3000 or h > 3000),
        "needs_contrast_boost": contrast < 45.0 or is_poor_lighting,
        "needs_denoise": blur_score > 300.0 or is_poor_lighting,
        "needs_sharpen": is_moderately_blurry and not is_very_blurry,
        "target_width": 2000,
    }

    return {
        "quality": quality_label,
        "score": max(0, score),
        "blur_score": round(blur_score, 2),
        "brightness": round(brightness, 2),
        "contrast": round(contrast, 2),
        "width": w,
        "height": h,
        "resolution": resolution,
        "recommendations": recommendations,
    }
