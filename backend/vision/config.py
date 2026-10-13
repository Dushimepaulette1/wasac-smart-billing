"""Where the models live and every guidance threshold, read from one JSON file."""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
ML_CODE_DIR = BACKEND_DIR / "ml"   # tracked: wasac_models.py, wasac_preprocessing.py, model_config.json
DEFAULT_GUIDANCE_PATH = Path(__file__).resolve().parent / "guidance_config.json"


def weights_dir() -> Path:
    """Where the .pt files are (not in git). Defaults to backend/ml."""
    return Path(os.getenv("ML_WEIGHTS_DIR") or ML_CODE_DIR)


def load_model_config() -> dict:
    with open(ML_CODE_DIR / "model_config.json") as f:
        return json.load(f)


def yolo_weights_name(model_config: dict) -> str:
    """model_config stores e.g. "best.pt (Benax YOLOv8, not included)"; the file name is the first word."""
    return model_config["cropper"]["yolo_weights"].split()[0]


@dataclass(frozen=True)
class GuidanceConfig:
    yolo_conf: float
    yolo_imgsz: int
    guide_imgsz: int
    crop_pad: float
    max_long_side: int
    guide_max_long_side: int
    thumbnail_max_width: int
    thumbnail_jpeg_quality: int
    no_meter_window_conf: float
    no_meter_min_digit_boxes: int
    too_far_min_width_frac: Optional[float]
    cut_off_edge_frac: Optional[float]
    too_dark_max_mean: Optional[float]
    glare_pixel_value: int
    glare_max_frac: Optional[float]
    blur_resize_height: int
    blurry_max_laplacian_var: Optional[float]
    hard_to_read_threshold: Optional[float]
    check_numbers_min_confidence: Optional[float]
    priority: List[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Optional[Path] = None, quality_threshold: Optional[float] = None) -> "GuidanceConfig":
        """A check whose threshold is null is off. hard_to_read_threshold "model" means model_config.json's."""
        with open(path or os.getenv("GUIDANCE_CONFIG_PATH") or DEFAULT_GUIDANCE_PATH) as f:
            raw = json.load(f)
        y, i, c = raw["yolo"], raw["image"], raw["checks"]
        return cls(
            yolo_conf=y["conf"],
            yolo_imgsz=y["imgsz"],
            guide_imgsz=y["guide_imgsz"],
            crop_pad=y["crop_pad"],
            max_long_side=i["max_long_side"],
            guide_max_long_side=i["guide_max_long_side"],
            thumbnail_max_width=i["thumbnail_max_width"],
            thumbnail_jpeg_quality=i["thumbnail_jpeg_quality"],
            no_meter_window_conf=c["no_meter_window_conf"],
            no_meter_min_digit_boxes=c["no_meter_min_digit_boxes"],
            too_far_min_width_frac=c["too_far_min_width_frac"],
            cut_off_edge_frac=c["cut_off_edge_frac"],
            too_dark_max_mean=c["too_dark_max_mean"],
            glare_pixel_value=c["glare_pixel_value"],
            glare_max_frac=c["glare_max_frac"],
            blur_resize_height=c["blur_resize_height"],
            blurry_max_laplacian_var=c["blurry_max_laplacian_var"],
            hard_to_read_threshold=(
                quality_threshold if c["hard_to_read_threshold"] == "model" else c["hard_to_read_threshold"]
            ),
            check_numbers_min_confidence=c["check_numbers_min_confidence"],
            priority=list(raw["priority"]),
        )
