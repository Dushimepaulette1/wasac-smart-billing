"""Photo guidance and the /submit-photo and /guide-frame pipelines, with the models faked.

Synthetic images exercise the brightness, glare and blur checks; fake YOLO / reader / gate objects
exercise the detection-based codes. No .pt files are needed.
"""
import base64
import dataclasses
import io

import cv2
import numpy as np
import pytest
from PIL import Image

import vision  # noqa: F401  puts backend/ml on sys.path
from vision.config import GuidanceConfig
from vision.guidance import (BLURRY, CHECK_NUMBERS, CUT_OFF, GLARE, HARD_TO_READ, NO_METER, OK, TOO_DARK,
                             TOO_FAR, Measurements, guidance_codes)
from vision.image_io import BadImage, load_bgr
from vision.models import ModelRegistry, get_registry
from vision.pipeline import analyze_photo, guide_frame

W, H = 1600, 1200
WINDOW = (400, 500, 1200, 700)  # a clearly visible number window, well inside the frame
WINDOW_CLS, DIGIT_CLS = 1, 2


# --- fakes ------------------------------------------------------------------

class _Arr:
    def __init__(self, a):
        self.a = np.asarray(a)

    def cpu(self):
        return self

    def numpy(self):
        return self.a


class _Boxes:
    def __init__(self, dets):
        self.cls = _Arr([d[0] for d in dets])
        self.xyxy = _Arr(np.asarray([d[1] for d in dets], dtype=float).reshape(-1, 4))
        self.conf = _Arr([d[2] for d in dets])
        self._n = len(dets)

    def __len__(self):
        return self._n


class FakeYolo:
    """Returns detections given in the coordinates of a W x H image, scaled to the actual input."""

    def __init__(self, dets):
        self.dets = dets

    def predict(self, source, **_):
        sx, sy = source.shape[1] / W, source.shape[0] / H
        scaled = [(c, (b[0] * sx, b[1] * sy, b[2] * sx, b[3] * sy), p) for c, b, p in self.dets]
        return [type("R", (), {"boxes": _Boxes(scaled) if scaled else None})()]


class FakeReader:
    def __init__(self, raw="565846", conf_min=0.95, conf_mean=0.97):
        self.raw, self.conf_min, self.conf_mean = raw, conf_min, conf_mean
        self.calls = 0

    def read(self, image):
        from wasac_preprocessing import digits_to_m3, pad_reading

        self.calls += 1
        padded = pad_reading(self.raw)
        return {"raw_digits": self.raw, "reading_digits": padded, "reading_m3": digits_to_m3(padded),
                "confidence_mean": self.conf_mean, "confidence_min": self.conf_min, "needs_check": padded is None}


class FakeGate:
    def __init__(self, score=0.1):
        self.value = score

    def score(self, image):
        return self.value


@pytest.fixture
def cfg():
    # BLURRY is off in the shipped config (calibration); give it a value so its logic is still tested.
    return dataclasses.replace(GuidanceConfig.load(quality_threshold=0.4289516615867615),
                               blurry_max_laplacian_var=80.0)


def registry(cfg, dets=((WINDOW_CLS, WINDOW, 0.9),), reader=None, gate=None, yolo=True):
    reg = ModelRegistry()
    reg.guidance = cfg
    reg.yolo = FakeYolo(list(dets)) if yolo else None
    reg.reader = reader if reader is not None else FakeReader()
    reg.quality_gate = gate if gate is not None else FakeGate()
    return reg


# --- synthetic images ---------------------------------------------------------

def meter_image(window=WINDOW, background=140):
    """Mid-grey frame with sharp black/white digit-like bars inside the window."""
    img = np.full((H, W, 3), background, np.uint8)
    x1, y1, x2, y2 = window
    region = img[y1:y2, x1:x2]
    region[:] = 235
    for x in range(10, region.shape[1] - 10, 40):
        region[30:-30, x:x + 14] = 15
    return img


def jpeg(img_bgr, quality=92) -> bytes:
    ok, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes()


def codes_for(img, reg, cfg):
    return analyze_photo(jpeg(img), reg, cfg).guidance


# --- each guidance code ------------------------------------------------------

def test_clear_meter_is_ok_and_read(cfg):
    reg = registry(cfg)
    r = analyze_photo(jpeg(meter_image()), reg, cfg)
    assert r.guidance == [OK]
    assert r.reading_digits == "00565846" and r.reading_m3 == pytest.approx(565.846)
    assert r.raw_digits == "565846" and r.confidence_min == 0.95 and not r.needs_check
    assert r.quality_score == pytest.approx(0.1)
    assert r.crop_method == "window" and not r.offer_manual_entry and r.models_ready
    thumb = cv2.imdecode(np.frombuffer(base64.b64decode(r.thumbnail_jpeg_base64), np.uint8), cv2.IMREAD_COLOR)
    assert thumb.shape[1] <= cfg.thumbnail_max_width


def test_no_meter_when_nothing_detected_and_reader_not_run(cfg):
    reader = FakeReader()
    reg = registry(cfg, dets=(), reader=reader)
    r = analyze_photo(jpeg(meter_image()), reg, cfg)
    assert r.guidance[0] == NO_METER
    assert reader.calls == 0 and r.reading_digits is None and r.offer_manual_entry
    assert r.thumbnail_jpeg_base64 is None and r.quality_score is None


def test_no_meter_with_weak_window_and_few_digits(cfg):
    dets = ((WINDOW_CLS, WINDOW, cfg.no_meter_window_conf - 0.1),
            (DIGIT_CLS, (450, 550, 500, 650), 0.5), (DIGIT_CLS, (520, 550, 570, 650), 0.5))
    assert codes_for(meter_image(), registry(cfg, dets=dets), cfg)[0] == NO_METER


def test_three_digit_boxes_are_enough_without_a_window(cfg):
    dets = tuple((DIGIT_CLS + i, (450 + 70 * i, 550, 500 + 70 * i, 650), 0.5) for i in range(3))
    r = analyze_photo(jpeg(meter_image()), registry(cfg, dets=dets), cfg)
    assert NO_METER not in r.guidance and r.crop_method == "digits" and r.reading_digits


def test_too_far(cfg):
    small = (760, 580, 760 + int(W * cfg.too_far_min_width_frac) - 40, 620)
    assert TOO_FAR in codes_for(meter_image(window=small), registry(cfg, dets=((WINDOW_CLS, small, 0.9),)), cfg)


def test_cut_off(cfg):
    edge = (0, 500, 800, 700)
    assert CUT_OFF in codes_for(meter_image(window=edge), registry(cfg, dets=((WINDOW_CLS, edge, 0.9),)), cfg)


def test_too_dark(cfg):
    dark = (meter_image() * 0.15).astype(np.uint8)
    assert TOO_DARK in codes_for(dark, registry(cfg), cfg)


def test_glare(cfg):
    img = meter_image()
    x1, y1, x2, y2 = WINDOW
    img[y1:y1 + 100, x1:x1 + 300] = 255  # a bright reflection over part of the window
    codes = codes_for(img, registry(cfg), cfg)
    assert GLARE in codes and TOO_DARK not in codes


def test_blurry(cfg):
    blurred = cv2.GaussianBlur(meter_image(), (0, 0), 12)
    assert BLURRY in codes_for(blurred, registry(cfg), cfg)
    assert BLURRY not in codes_for(meter_image(), registry(cfg), cfg)


def test_hard_to_read(cfg):
    assert HARD_TO_READ in codes_for(meter_image(), registry(cfg, gate=FakeGate(cfg.hard_to_read_threshold)), cfg)
    assert HARD_TO_READ not in codes_for(meter_image(), registry(cfg, gate=FakeGate(0.2)), cfg)


def test_check_numbers_low_confidence(cfg):
    r = analyze_photo(jpeg(meter_image()), registry(cfg, reader=FakeReader(conf_min=0.3)), cfg)
    assert r.guidance == [CHECK_NUMBERS] and r.reading_digits  # still suggested, just flagged


def test_check_numbers_impossible_length(cfg):
    r = analyze_photo(jpeg(meter_image()), registry(cfg, reader=FakeReader(raw="1234567890")), cfg)
    assert CHECK_NUMBERS in r.guidance and r.needs_check
    assert r.reading_digits is None and r.offer_manual_entry


def test_codes_are_ordered_most_important_first(cfg):
    m = Measurements(image_w=W, image_h=H, window_conf=0.9, box=(0, 500, 200, 700), box_method="window",
                     region_mean=30, glare_frac=0.5, laplacian_var=1, quality_score=0.9, confidence_min=0.1)
    assert guidance_codes(m, cfg) == [TOO_FAR, CUT_OFF, TOO_DARK, GLARE, BLURRY, HARD_TO_READ, CHECK_NUMBERS]


def test_no_meter_suppresses_window_and_reading_codes(cfg):
    m = Measurements(image_w=W, image_h=H, box=None, region_mean=30, laplacian_var=1000, confidence_min=0.1)
    assert guidance_codes(m, cfg) == [NO_METER, TOO_DARK]


# --- image handling ----------------------------------------------------------

def test_exif_rotation_is_applied():
    img = Image.new("RGB", (400, 200), "white")
    exif = img.getexif()
    exif[0x0112] = 6  # "rotate 90 CW to display": a phone held upright
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes())
    assert load_bgr(buf.getvalue(), 1600).shape[:2] == (400, 200)


def test_long_side_is_capped():
    assert max(load_bgr(jpeg(np.zeros((3000, 4000, 3), np.uint8)), 1600).shape[:2]) == 1600


def test_bad_image_raises():
    with pytest.raises(BadImage):
        load_bgr(b"not an image", 1600)


def test_oversized_image_is_a_bad_image_not_a_crash(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)  # Pillow refuses anything over 2x this
    with pytest.raises(BadImage, match="too large"):
        load_bgr(jpeg(np.zeros((300, 400, 3), np.uint8)), 1600)


def test_large_jpeg_is_decoded_at_reduced_scale_with_exif_rotation():
    img = Image.new("RGB", (6000, 3000), "white")
    exif = img.getexif()
    exif[0x0112] = 6
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes())
    assert load_bgr(buf.getvalue(), 1600).shape[:2] == (1600, 800)


# --- guide frame --------------------------------------------------------------

def test_guide_frame_returns_box_in_unit_coordinates(cfg):
    reader, gate = FakeReader(), FakeGate()
    reg = registry(cfg, reader=reader, gate=gate)
    small = cv2.resize(meter_image(), (640, 480))
    f = guide_frame(jpeg(small), reg, cfg)
    assert f.available and f.guidance == [OK] and f.box_method == "window"
    assert f.box == pytest.approx({"x1": 0.25, "y1": 0.4167, "x2": 0.75, "y2": 0.5833}, abs=0.01)
    assert reader.calls == 0  # frames never run the reader


def test_guide_frame_flags_dark_frames(cfg):
    dark = (cv2.resize(meter_image(), (640, 480)) * 0.1).astype(np.uint8)
    assert TOO_DARK in guide_frame(jpeg(dark), registry(cfg), cfg).guidance


# --- missing models -----------------------------------------------------------

def test_missing_models_offer_manual_entry_without_claiming_no_meter(cfg):
    reg = registry(cfg, yolo=False)
    reg.reader = None
    r = analyze_photo(jpeg(meter_image()), reg, cfg)
    assert not r.models_ready and r.offer_manual_entry and r.reading_digits is None
    assert NO_METER not in r.guidance


def test_registry_reports_missing_files(tmp_path):
    reg = ModelRegistry().load(tmp_path)
    assert not reg.ready
    assert all(s.state == "missing" for s in reg.status.values())


# --- API ----------------------------------------------------------------------

@pytest.fixture
def photo_client(client, cfg):
    """Signed in (the photo endpoints need a household or staff sign-in)."""
    from main import app

    holder = {"reg": registry(cfg)}
    app.dependency_overrides[get_registry] = lambda: holder["reg"]
    yield client, holder


def test_photo_endpoints_need_a_sign_in(anon_client):
    assert anon_client.post("/submit-photo", files={"file": ("m.jpg", b"x", "image/jpeg")}).status_code == 401
    assert anon_client.post("/guide-frame", files={"file": ("m.jpg", b"x", "image/jpeg")}).status_code == 401


def test_submit_photo_endpoint(photo_client):
    client, _ = photo_client
    body = client.post("/submit-photo", files={"file": ("m.jpg", jpeg(meter_image()), "image/jpeg")}).json()
    assert body["status"] == "readable" and body["predicted_reading"] == "565846"
    assert body["confidence"] == 0.95 and body["quality_gate_score"] == pytest.approx(0.1)
    assert body["reading_digits"] == "00565846" and body["guidance"] == ["OK"]
    assert body["thumbnail_jpeg_base64"] and "measurements" not in body


def test_submit_photo_no_meter_is_unreadable_not_an_error(photo_client, cfg):
    client, holder = photo_client
    holder["reg"] = registry(cfg, dets=())
    r = client.post("/submit-photo", files={"file": ("m.jpg", jpeg(meter_image()), "image/jpeg")})
    assert r.status_code == 200
    assert r.json()["status"] == "unreadable" and r.json()["guidance"][0] == "NO_METER"
    assert r.json()["offer_manual_entry"]


def test_submit_photo_models_missing(photo_client):
    client, holder = photo_client
    holder["reg"] = ModelRegistry()
    body = client.post("/submit-photo", files={"file": ("m.jpg", jpeg(meter_image()), "image/jpeg")}).json()
    assert body["models_ready"] is False and body["offer_manual_entry"] and body["status"] == "unreadable"


def test_submit_photo_rejects_non_images(photo_client):
    client, _ = photo_client
    assert client.post("/submit-photo", files={"file": ("x.jpg", b"nope", "image/jpeg")}).status_code == 422


def test_guide_frame_endpoint(photo_client):
    client, _ = photo_client
    small = cv2.resize(meter_image(), (640, 480))
    body = client.post("/guide-frame", files={"file": ("f.jpg", jpeg(small), "image/jpeg")}).json()
    assert body["available"] and body["guidance"] == ["OK"] and body["box"]["x1"] == pytest.approx(0.25, abs=0.01)


def test_health_reports_model_state(anon_client):
    from vision.models import registry as live

    body = anon_client.get("/health").json()
    assert body["photo_reading"] in ("ready", "manual_entry_only")
    assert body["yolo_model"] == live.status["yolo"].label()
