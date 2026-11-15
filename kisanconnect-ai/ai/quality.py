"""AI quality grading of produce photos (Grade A / B / C).

Computer-vision scoring with Pillow + NumPy: colour richness, brightness,
sharpness, colour uniformity and dark-blemish ratio. Swap in a trained CNN
later by keeping the same `analyze_quality()` return shape.
"""
import numpy as np
from PIL import Image, ImageFilter


def analyze_quality(file_or_path):
    img = Image.open(file_or_path).convert("RGB")
    img.thumbnail((320, 320))
    hsv = np.asarray(img.convert("HSV"), dtype=np.float32) / 255.0
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]

    fg = (s > 0.18) & (v > 0.12)
    if fg.mean() < 0.05:
        fg = np.ones_like(fg, dtype=bool)

    saturation = float(s[fg].mean())
    brightness = float(v[fg].mean())
    ang = 2 * np.pi * h[fg]
    mu = (np.arctan2(np.sin(ang).mean(), np.cos(ang).mean()) / (2 * np.pi)) % 1.0
    diff = np.abs(h - mu)
    diff = np.minimum(diff, 1 - diff) * 360
    blemish_mask = fg & ((v < 0.28) | ((diff > 25) & (v < 0.60)))
    blemish = float(blemish_mask.sum() / max(fg.sum(), 1))
    edges = np.asarray(img.convert("L").filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    sharp = float(min(edges.var() / 600.0, 1.0))
    uniformity = float(np.hypot(np.cos(ang).mean(), np.sin(ang).mean()))

    score = 100 * (
        0.25 * min(saturation / 0.6, 1.0)
        + 0.15 * float(np.clip((brightness - 0.25) / 0.5, 0, 1))
        + 0.15 * sharp
        + 0.15 * uniformity
        + 0.30 * (1 - min(blemish * 4, 1.0))
    )
    score = float(np.clip(score, 0, 100))
    grade = "A" if score >= 72 else "B" if score >= 52 else "C"

    tips = []
    if brightness < 0.45:
        tips.append("Photo looks dark. Retake it in daylight for a fairer grade.")
    if sharp < 0.25:
        tips.append("Photo looks blurry. Hold the phone steady and focus on the produce.")
    if blemish > 0.15:
        tips.append("Dark patches found. Sort out damaged pieces before listing.")
    if uniformity < 0.6:
        tips.append("Colours are mixed. Sorting by ripeness or size can lift the grade.")
    if not tips:
        tips.append("Clear photo and healthy colour. This lot is ready to list.")

    return {
        "grade": grade, "score": round(score), "tips": tips,
        "details": {
            "colour": round(min(saturation / 0.6, 1.0) * 100),
            "brightness": round(float(np.clip((brightness - 0.25) / 0.5, 0, 1)) * 100),
            "sharpness": round(sharp * 100),
            "uniformity": round(uniformity * 100),
            "blemish_free": round((1 - min(blemish * 4, 1.0)) * 100),
        },
    }
