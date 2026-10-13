"""Photo guidance: measure a photo, then turn the numbers into ordered guidance codes.

Codes never block a submission. NO_METER only means no reading is suggested.
"""
from dataclasses import asdict, dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from vision.config import GuidanceConfig
from wasac_preprocessing import DIGIT_CLASSES, DISPLAY_CLASS

NO_METER = "NO_METER"
TOO_FAR = "TOO_FAR"
CUT_OFF = "CUT_OFF"
TOO_DARK = "TOO_DARK"
GLARE = "GLARE"
BLURRY = "BLURRY"
HARD_TO_READ = "HARD_TO_READ"
CHECK_NUMBERS = "CHECK_NUMBERS"
OK = "OK"

Box = Tuple[int, int, int, int]


@dataclass
class Measurements:
    image_w: int
    image_h: int
    window_conf: float = 0.0
    digit_boxes: int = 0
    box: Optional[Box] = None          # unpadded number-window box, only for 'window'/'digits' methods
    box_method: str = "none"
    region_mean: float = 0.0
    glare_frac: float = 0.0
    laplacian_var: float = 0.0
    quality_score: Optional[float] = None
    confidence_min: Optional[float] = None
    needs_check: Optional[bool] = None

    def to_dict(self) -> dict:
        return asdict(self)


def summarise_detections(cls: np.ndarray, confs: np.ndarray) -> Tuple[float, int]:
    windows = confs[cls == DISPLAY_CLASS]
    return (float(windows.max()) if windows.size else 0.0), int(np.isin(cls, list(DIGIT_CLASSES)).sum())


def measure_region(region_bgr: np.ndarray, cfg: GuidanceConfig) -> Tuple[float, float, float]:
    """(mean brightness 0-255, fraction of near-white pixels, Laplacian variance at a fixed height)."""
    gray = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    scaled = cv2.resize(gray, (max(1, round(w * cfg.blur_resize_height / h)), cfg.blur_resize_height),
                        interpolation=cv2.INTER_AREA if h > cfg.blur_resize_height else cv2.INTER_LINEAR)
    return (
        float(gray.mean()),
        float((gray >= cfg.glare_pixel_value).mean()),
        float(cv2.Laplacian(scaled, cv2.CV_64F).var()),
    )


def is_no_meter(m: Measurements, cfg: GuidanceConfig) -> bool:
    return m.window_conf < cfg.no_meter_window_conf and m.digit_boxes < cfg.no_meter_min_digit_boxes


def guidance_codes(m: Measurements, cfg: GuidanceConfig, has_detections: bool = True) -> List[str]:
    """Every code that applies, most important first (cfg.priority); [OK] when none do.

    has_detections=False (YOLO unavailable) skips the codes that depend on finding the window.
    """
    fired = set()
    no_meter = has_detections and is_no_meter(m, cfg)
    if no_meter:
        fired.add(NO_METER)
    elif m.box is not None:
        x1, y1, x2, y2 = m.box
        if (x2 - x1) / m.image_w < cfg.too_far_min_width_frac:
            fired.add(TOO_FAR)
        ex, ey = cfg.cut_off_edge_frac * m.image_w, cfg.cut_off_edge_frac * m.image_h
        if x1 <= ex or y1 <= ey or x2 >= m.image_w - ex or y2 >= m.image_h - ey:
            fired.add(CUT_OFF)
    if m.region_mean < cfg.too_dark_max_mean:
        fired.add(TOO_DARK)
    if m.glare_frac > cfg.glare_max_frac:
        fired.add(GLARE)
    if m.laplacian_var < cfg.blurry_max_laplacian_var:
        fired.add(BLURRY)
    if m.quality_score is not None and cfg.hard_to_read_threshold is not None \
            and m.quality_score >= cfg.hard_to_read_threshold:
        fired.add(HARD_TO_READ)
    if not no_meter and (m.needs_check or (m.confidence_min is not None
                                           and m.confidence_min < cfg.check_numbers_min_confidence)):
        fired.add(CHECK_NUMBERS)
    ordered = [code for code in cfg.priority if code in fired]
    return ordered or [OK]
