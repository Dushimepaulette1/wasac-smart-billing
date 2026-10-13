"""Guidance config switches, the quality gate's class index, and the weight download helper."""
import dataclasses
import http.server
import importlib.util
import json
import threading
from pathlib import Path

import pytest

import vision  # noqa: F401
from vision.config import GuidanceConfig, load_model_config
from vision.guidance import BLURRY, GLARE, OK, TOO_DARK, Measurements, guidance_codes

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dl = _load_script("download_models")


# --- config -----------------------------------------------------------------------

def test_null_threshold_turns_a_check_off():
    cfg = dataclasses.replace(GuidanceConfig.load(quality_threshold=0.43), blurry_max_laplacian_var=80.0)
    bad = Measurements(image_w=100, image_h=100, window_conf=0.9, region_mean=5, glare_frac=0.9, laplacian_var=0)
    assert {TOO_DARK, GLARE, BLURRY} <= set(guidance_codes(bad, cfg))
    off = dataclasses.replace(cfg, too_dark_max_mean=None, glare_max_frac=None, blurry_max_laplacian_var=None)
    assert guidance_codes(bad, off) == [OK]


def test_shipped_config_matches_the_calibration():
    cfg = GuidanceConfig.load(quality_threshold=0.43)
    assert cfg.blurry_max_laplacian_var is None  # off: it fired more on readable photos
    assert cfg.no_meter_window_conf == 0.35 and cfg.guide_imgsz == 640
    assert cfg.hard_to_read_threshold == 0.5 and cfg.check_numbers_min_confidence == 0.5


def test_hard_to_read_model_value_uses_model_config(tmp_path):
    raw = json.loads((Path(vision.__file__).parent / "guidance_config.json").read_text())
    raw["checks"]["hard_to_read_threshold"] = "model"
    path = tmp_path / "g.json"
    path.write_text(json.dumps(raw))
    assert GuidanceConfig.load(path, quality_threshold=0.4289).hard_to_read_threshold == 0.4289
    raw["checks"]["hard_to_read_threshold"] = None
    path.write_text(json.dumps(raw))
    assert GuidanceConfig.load(path, quality_threshold=0.4289).hard_to_read_threshold is None


def test_quality_gate_reads_its_class_index_from_model_config(tmp_path):
    import torch
    import torchvision
    from PIL import Image

    from vision.models import QualityGate

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


# --- download helper ----------------------------------------------------------------

@pytest.mark.parametrize("link", [
    "https://drive.google.com/file/d/1AbC_d-9/view?usp=sharing",
    "https://drive.google.com/open?id=1AbC_d-9",
    "https://drive.google.com/uc?export=download&id=1AbC_d-9",
])
def test_drive_links_become_direct_downloads(link):
    assert dl.direct_url(link) == "https://drive.usercontent.google.com/download?id=1AbC_d-9&export=download&confirm=t"


def test_other_urls_are_unchanged():
    assert dl.direct_url("https://example.org/m/best.pt") == "https://example.org/m/best.pt"


def test_parse_urls():
    assert dl.parse_urls("best.pt=https://a/x?id=1&y=2, quality_gate.pt=https://b") == {
        "best.pt": "https://a/x?id=1&y=2", "quality_gate.pt": "https://b"}
    with pytest.raises(SystemExit):
        dl.parse_urls("no-equals-sign")


@pytest.fixture
def server(tmp_path):
    (tmp_path / "w.pt").write_bytes(b"weights")
    (tmp_path / "page.html").write_text("<html>sign in</html>")
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(tmp_path), **k)  # noqa: E731
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    handler_log = http.server.SimpleHTTPRequestHandler.log_message
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    http.server.SimpleHTTPRequestHandler.log_message = handler_log


def test_download_verifies_checksum(server, tmp_path):
    import hashlib

    dest = tmp_path / "out" / "w.pt"
    dest.parent.mkdir()
    dl.download(f"{server}/w.pt", dest, hashlib.sha256(b"weights").hexdigest())
    assert dest.read_bytes() == b"weights"


def test_download_rejects_wrong_checksum_and_saves_nothing(server, tmp_path):
    dest = tmp_path / "w2.pt"
    with pytest.raises(SystemExit, match="Checksum mismatch"):
        dl.download(f"{server}/w.pt", dest, "0" * 64)
    assert not dest.exists() and not dest.with_suffix(".pt.part").exists()


def test_download_rejects_a_web_page(server, tmp_path):
    with pytest.raises(SystemExit, match="web page"):
        dl.download(f"{server}/page.html", tmp_path / "x.pt", "0" * 64)
