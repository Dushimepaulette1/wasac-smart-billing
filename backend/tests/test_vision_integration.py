"""Runs the real models end to end. Skipped unless the three .pt files are present
(python scripts/download_models.py). Loading them takes a while on a cold start."""
import cv2
import numpy as np
import pytest

import app.vision  # noqa: F401  puts backend/ml on sys.path
from app.vision.config import load_model_config, weights_dir, yolo_weights_name
from app.vision.guidance import NO_METER
from app.vision.models import ModelRegistry
from app.vision.pipeline import analyze_photo, guide_frame

_cfg = load_model_config()
_WEIGHTS = [yolo_weights_name(_cfg), _cfg["reader"]["weights"], _cfg["quality_gate"]["weights"]]
pytestmark = pytest.mark.skipif(
    not all((weights_dir() / name).exists() for name in _WEIGHTS),
    reason="model weights not downloaded (scripts/download_models.py)",
)


@pytest.fixture(scope="module")
def real():
    return ModelRegistry().load()


def jpeg(img):
    return cv2.imencode(".jpg", img)[1].tobytes()


def test_all_three_models_load(real):
    assert real.ready and real.quality_gate is not None
    assert {s.state for s in real.status.values()} == {"loaded"}


def test_blank_photo_is_no_meter_and_skips_the_reader(real):
    r = analyze_photo(jpeg(np.full((1200, 1600, 3), 128, np.uint8)), real, real.guidance_config())
    assert r.guidance[0] == NO_METER
    assert r.reading_digits is None and r.offer_manual_entry and r.quality_score is None


def test_reader_and_gate_run_on_a_crop(real):
    crop = np.full((150, 600, 3), 235, np.uint8)
    for x in range(10, 590, 40):
        crop[30:-30, x:x + 14] = 15
    from app.vision.image_io import bgr_to_pil

    read = real.reader.read(bgr_to_pil(crop))
    assert set(read) >= {"raw_digits", "reading_digits", "reading_m3", "confidence_min", "confidence_mean"}
    assert 0.0 <= real.quality_gate.score(bgr_to_pil(crop)) <= 1.0


def test_guide_frame_runs(real):
    f = guide_frame(jpeg(np.full((480, 640, 3), 128, np.uint8)), real, real.guidance_config())
    assert f.available and f.guidance[0] == NO_METER and f.box is None
