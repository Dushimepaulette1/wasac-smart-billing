"""The /submit-photo and /guide-frame pipelines."""
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from vision.config import GuidanceConfig
from vision.guidance import Measurements, guidance_codes, is_no_meter, measure_region, summarise_detections
from vision.image_io import bgr_to_pil, jpeg_base64, load_bgr
from vision.models import ModelRegistry
from wasac_preprocessing import crop_box, detect, display_box

BOX_METHODS = ("window", "digits")


@dataclass
class PhotoResult:
    models_ready: bool
    offer_manual_entry: bool
    guidance: List[str]
    raw_digits: Optional[str] = None
    reading_digits: Optional[str] = None
    reading_m3: Optional[float] = None
    confidence_min: Optional[float] = None
    confidence_mean: Optional[float] = None
    needs_check: bool = False
    quality_score: Optional[float] = None
    crop_method: str = "none"
    thumbnail_jpeg_base64: Optional[str] = None
    measurements: dict = field(default_factory=dict)
    timings_ms: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FrameResult:
    available: bool
    guidance: List[str]
    box: Optional[Dict[str, float]] = None   # number window in 0-1 image coordinates
    box_method: str = "none"
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class _Clock:
    def __init__(self):
        self.t = time.perf_counter()
        self.marks: Dict[str, float] = {}

    def lap(self, name: str) -> None:
        now = time.perf_counter()
        self.marks[name] = round((now - self.t) * 1000, 1)
        self.t = now


def _locate(img, registry: ModelRegistry, cfg: GuidanceConfig, imgsz: int):
    """Run YOLO and measure brightness/glare/blur on the window (or the whole frame if none)."""
    h, w = img.shape[:2]
    m = Measurements(image_w=w, image_h=h)
    crop = None
    if registry.yolo is not None:
        cls, xyxy, confs = detect(img, registry.yolo, cfg.yolo_conf, imgsz, "cpu")
        m.window_conf, m.digit_boxes = summarise_detections(cls, confs)
        box, m.box_method = display_box(cls, xyxy, confs, w, h)
        if m.box_method in BOX_METHODS:
            m.box = tuple(int(v) for v in box)
        if box is not None:
            crop = crop_box(img, box, cfg.crop_pad)
    m.region_mean, m.glare_frac, m.laplacian_var = measure_region(crop if crop is not None else img, cfg)
    return m, crop


def analyze_photo(data: bytes, registry: ModelRegistry, cfg: GuidanceConfig) -> PhotoResult:
    """EXIF fix -> resize -> YOLO crop -> guidance checks -> quality gate -> reader -> pad_reading."""
    clock = _Clock()
    img = load_bgr(data, cfg.max_long_side)
    clock.lap("decode")
    m, crop = _locate(img, registry, cfg, cfg.yolo_imgsz)
    clock.lap("locate")

    has_detections = registry.yolo is not None
    no_meter = has_detections and is_no_meter(m, cfg)
    result = PhotoResult(models_ready=registry.ready, offer_manual_entry=True, guidance=[],
                         crop_method=m.box_method)

    if registry.ready and not no_meter and crop is not None:
        pil_crop = bgr_to_pil(crop)
        if registry.quality_gate is not None:
            m.quality_score = round(registry.quality_gate.score(pil_crop), 4)
            clock.lap("quality_gate")
        read = registry.reader.read(pil_crop)
        clock.lap("reader")
        m.confidence_min, m.needs_check = read["confidence_min"], read["needs_check"]
        result.raw_digits = read["raw_digits"]
        result.reading_digits = read["reading_digits"]
        result.reading_m3 = read["reading_m3"]
        result.confidence_min = read["confidence_min"]
        result.confidence_mean = read["confidence_mean"]
        result.needs_check = read["needs_check"]
        result.thumbnail_jpeg_base64 = jpeg_base64(crop, cfg.thumbnail_max_width, cfg.thumbnail_jpeg_quality)
        clock.lap("thumbnail")

    result.quality_score = m.quality_score
    result.guidance = guidance_codes(m, cfg, has_detections=has_detections)
    result.offer_manual_entry = result.reading_digits is None
    result.measurements = m.to_dict()
    result.timings_ms = {**clock.marks, "total": round(sum(clock.marks.values()), 1)}
    return result


def guide_frame(data: bytes, registry: ModelRegistry, cfg: GuidanceConfig) -> FrameResult:
    """Live framing hints: YOLO plus brightness/glare/blur only. No quality gate, no reader."""
    start = time.perf_counter()
    img = load_bgr(data, cfg.guide_max_long_side)
    m, _ = _locate(img, registry, cfg, cfg.guide_imgsz)
    box = None
    if m.box is not None:
        x1, y1, x2, y2 = m.box
        box = {"x1": round(x1 / m.image_w, 4), "y1": round(y1 / m.image_h, 4),
               "x2": round(x2 / m.image_w, 4), "y2": round(y2 / m.image_h, 4)}
    return FrameResult(
        available=registry.yolo is not None,
        guidance=guidance_codes(m, cfg, has_detections=registry.yolo is not None),
        box=box,
        box_method=m.box_method,
        elapsed_ms=round((time.perf_counter() - start) * 1000, 1),
    )
