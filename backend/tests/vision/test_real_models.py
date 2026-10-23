"""Runs the real models end to end. Skipped unless the three .pt files are present
(python scripts/download_models.py). Loading them takes a while on a cold start."""
import cv2
import numpy as np
import pytest
from app.vision.guidance import NO_METER
from app.vision.models import ModelRegistry
from app.vision.pipeline import analyze_photo, guide_frame


@pytest.fixture(scope="module")
def real():
    registry = ModelRegistry().load()
    if not registry.ready:  # e.g. CI: the weights are private and never in the repository
        pytest.skip("model files not present")
    return registry


def jpeg(img):
    return cv2.imencode(".jpg", img)[1].tobytes()


def test_when_the_real_weights_are_present_should_load_all_three_models(real):
    assert real.ready and real.quality_gate is not None
    assert {s.state for s in real.status.values()} == {"loaded"}


def test_when_the_photo_is_blank_should_say_no_meter_and_skip_the_reader(real):
    r = analyze_photo(jpeg(np.full((1200, 1600, 3), 128, np.uint8)), real, real.guidance_config())
    assert r.guidance[0] == NO_METER
    assert r.reading_digits is None and r.offer_manual_entry and r.quality_score is None


def test_when_given_a_crop_should_run_the_reader_and_the_gate(real):
    crop = np.full((150, 600, 3), 235, np.uint8)
    for x in range(10, 590, 40):
        crop[30:-30, x:x + 14] = 15
    from app.vision.image_io import bgr_to_pil

    read = real.reader.read(bgr_to_pil(crop))
    assert set(read) >= {"raw_digits", "reading_digits", "reading_m3", "confidence_min", "confidence_mean"}
    assert 0.0 <= real.quality_gate.score(bgr_to_pil(crop)) <= 1.0


def test_when_giving_live_tips_with_real_models_should_run(real):
    f = guide_frame(jpeg(np.full((480, 640, 3), 128, np.uint8)), real, real.guidance_config())
    assert f.available and f.guidance[0] == NO_METER and f.box is None
