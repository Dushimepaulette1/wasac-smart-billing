"""The calibrated guidance settings (app/vision/config.py, guidance_config.json)."""
import dataclasses
import json
from pathlib import Path
import pytest
from app import vision
from app.vision.config import GuidanceConfig, load_model_config
from app.vision.guidance import BLURRY, GLARE, OK, TOO_DARK, Measurements, guidance_codes


def test_when_a_threshold_is_null_should_turn_that_check_off():
    cfg = dataclasses.replace(GuidanceConfig.load(quality_threshold=0.43), blurry_max_laplacian_var=80.0)
    bad = Measurements(image_w=100, image_h=100, window_conf=0.9, region_mean=5, glare_frac=0.9, laplacian_var=0)
    assert {TOO_DARK, GLARE, BLURRY} <= set(guidance_codes(bad, cfg))
    off = dataclasses.replace(cfg, too_dark_max_mean=None, glare_max_frac=None, blurry_max_laplacian_var=None)
    assert guidance_codes(bad, off) == [OK]


def test_when_loading_the_shipped_config_should_match_the_calibration():
    cfg = GuidanceConfig.load(quality_threshold=0.43)
    assert cfg.blurry_max_laplacian_var is None  # off: it fired more on readable photos
    assert cfg.no_meter_window_conf == 0.35 and cfg.guide_imgsz == 640
    assert cfg.hard_to_read_threshold == 0.5 and cfg.check_numbers_min_confidence == 0.5


def test_when_hard_to_read_says_model_should_use_the_model_config_threshold(tmp_path):
    raw = json.loads((Path(vision.__file__).parent / "guidance_config.json").read_text())
    raw["checks"]["hard_to_read_threshold"] = "model"
    path = tmp_path / "g.json"
    path.write_text(json.dumps(raw))
    assert GuidanceConfig.load(path, quality_threshold=0.4289).hard_to_read_threshold == 0.4289
    raw["checks"]["hard_to_read_threshold"] = None
    path.write_text(json.dumps(raw))
    assert GuidanceConfig.load(path, quality_threshold=0.4289).hard_to_read_threshold is None


def test_when_loading_the_quality_gate_should_read_its_class_index_from_model_config(tmp_path):
    import torch
    import torchvision
    from PIL import Image

    from app.vision.models import QualityGate

    assert load_model_config()["quality_gate"]["positive_class_index"] == 1
    model = torchvision.models.mobilenet_v2(weights=None)
    model.classifier[1] = torch.nn.Linear(model.last_channel, 2)
    weights = tmp_path / "gate.pt"
    torch.save(model.state_dict(), weights)
    gate_cfg = dict(load_model_config()["quality_gate"])
    img = Image.new("RGB", (384, 128), "gray")
    p1 = QualityGate(weights, gate_cfg).score(img)
    p0 = QualityGate(weights, dict(gate_cfg, positive_class_index=0)).score(img)
    assert p0 + p1 == pytest.approx(1.0, abs=1e-5)
