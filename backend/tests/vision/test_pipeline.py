"""The photo pipeline, live guidance, image loading and model loading (app/vision/)."""
import base64
import io
import cv2
import numpy as np
import pytest
from PIL import Image
from app.vision.guidance import (
    BLURRY,
    CHECK_NUMBERS,
    CUT_OFF,
    GLARE,
    HARD_TO_READ,
    NO_METER,
    OK,
    TOO_DARK,
    TOO_FAR,
    Measurements,
    guidance_codes,
)
from app.vision.image_io import BadImage, load_bgr
from app.vision.models import ModelRegistry
from app.vision.pipeline import analyze_photo, guide_frame
from support.vision_fakes import (
    DIGIT_CLS,
    H,
    W,
    WINDOW,
    WINDOW_CLS,
    FakeGate,
    FakeReader,
    codes_for,
    jpeg,
    meter_image,
    registry,
)


def test_when_the_meter_is_clear_should_say_ok_and_read_it(cfg):
    reg = registry(cfg)
    r = analyze_photo(jpeg(meter_image()), reg, cfg)
    assert r.guidance == [OK]
    assert r.reading_digits == "00565846" and r.reading_m3 == pytest.approx(565.846)
    assert r.raw_digits == "565846" and r.confidence_min == 0.95 and not r.needs_check
    assert r.quality_score == pytest.approx(0.1)
    assert r.crop_method == "window" and not r.offer_manual_entry and r.models_ready
    thumb = cv2.imdecode(np.frombuffer(base64.b64decode(r.thumbnail_jpeg_base64), np.uint8), cv2.IMREAD_COLOR)
    assert thumb.shape[1] <= cfg.thumbnail_max_width


def test_when_nothing_is_detected_should_say_no_meter_and_skip_the_reader(cfg):
    reader = FakeReader()
    reg = registry(cfg, dets=(), reader=reader)
    r = analyze_photo(jpeg(meter_image()), reg, cfg)
    assert r.guidance[0] == NO_METER
    assert reader.calls == 0 and r.reading_digits is None and r.offer_manual_entry
    assert r.thumbnail_jpeg_base64 is None and r.quality_score is None


def test_when_the_window_is_weak_and_digits_few_should_say_no_meter(cfg):
    dets = ((WINDOW_CLS, WINDOW, cfg.no_meter_window_conf - 0.1),
            (DIGIT_CLS, (450, 550, 500, 650), 0.5), (DIGIT_CLS, (520, 550, 570, 650), 0.5))
    assert codes_for(meter_image(), registry(cfg, dets=dets), cfg)[0] == NO_METER


def test_when_three_digits_are_found_without_a_window_should_still_find_the_meter(cfg):
    dets = tuple((DIGIT_CLS + i, (450 + 70 * i, 550, 500 + 70 * i, 650), 0.5) for i in range(3))
    r = analyze_photo(jpeg(meter_image()), registry(cfg, dets=dets), cfg)
    assert NO_METER not in r.guidance and r.crop_method == "digits" and r.reading_digits


def test_when_the_window_is_small_in_the_photo_should_say_too_far(cfg):
    small = (760, 580, 760 + int(W * cfg.too_far_min_width_frac) - 40, 620)
    assert TOO_FAR in codes_for(meter_image(window=small), registry(cfg, dets=((WINDOW_CLS, small, 0.9),)), cfg)


def test_when_the_window_touches_the_edge_should_say_cut_off(cfg):
    edge = (0, 500, 800, 700)
    assert CUT_OFF in codes_for(meter_image(window=edge), registry(cfg, dets=((WINDOW_CLS, edge, 0.9),)), cfg)


def test_when_the_photo_is_dark_should_say_too_dark(cfg):
    dark = (meter_image() * 0.15).astype(np.uint8)
    assert TOO_DARK in codes_for(dark, registry(cfg), cfg)


def test_when_there_is_glare_should_say_glare(cfg):
    img = meter_image()
    x1, y1, x2, y2 = WINDOW
    img[y1:y1 + 100, x1:x1 + 300] = 255  # a bright reflection over part of the window
    codes = codes_for(img, registry(cfg), cfg)
    assert GLARE in codes and TOO_DARK not in codes


def test_when_the_photo_is_blurry_should_say_blurry(cfg):
    blurred = cv2.GaussianBlur(meter_image(), (0, 0), 12)
    assert BLURRY in codes_for(blurred, registry(cfg), cfg)
    assert BLURRY not in codes_for(meter_image(), registry(cfg), cfg)


def test_when_the_quality_gate_is_unsure_should_say_hard_to_read(cfg):
    assert HARD_TO_READ in codes_for(meter_image(), registry(cfg, gate=FakeGate(cfg.hard_to_read_threshold)), cfg)
    assert HARD_TO_READ not in codes_for(meter_image(), registry(cfg, gate=FakeGate(0.2)), cfg)


def test_when_the_reader_is_unsure_should_ask_to_check_the_numbers(cfg):
    r = analyze_photo(jpeg(meter_image()), registry(cfg, reader=FakeReader(conf_min=0.3)), cfg)
    assert r.guidance == [CHECK_NUMBERS] and r.reading_digits  # still suggested, just flagged


def test_when_the_reading_length_is_impossible_should_ask_to_check_the_numbers(cfg):
    r = analyze_photo(jpeg(meter_image()), registry(cfg, reader=FakeReader(raw="1234567890")), cfg)
    assert CHECK_NUMBERS in r.guidance and r.needs_check
    assert r.reading_digits is None and r.offer_manual_entry


def test_when_several_tips_apply_should_put_the_most_important_first(cfg):
    m = Measurements(image_w=W, image_h=H, window_conf=0.9, box=(0, 500, 200, 700), box_method="window",
                     region_mean=30, glare_frac=0.5, laplacian_var=1, quality_score=0.9, confidence_min=0.1)
    assert guidance_codes(m, cfg) == [TOO_FAR, CUT_OFF, TOO_DARK, GLARE, BLURRY, HARD_TO_READ, CHECK_NUMBERS]


def test_when_there_is_no_meter_should_drop_window_and_reading_tips(cfg):
    m = Measurements(image_w=W, image_h=H, box=None, region_mean=30, laplacian_var=1000, confidence_min=0.1)
    assert guidance_codes(m, cfg) == [NO_METER, TOO_DARK]


def test_when_the_photo_has_exif_rotation_should_apply_it():
    img = Image.new("RGB", (400, 200), "white")
    exif = img.getexif()
    exif[0x0112] = 6  # "rotate 90 CW to display": a phone held upright
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes())
    assert load_bgr(buf.getvalue(), 1600).shape[:2] == (400, 200)


def test_when_the_photo_is_large_should_cap_the_long_side():
    assert max(load_bgr(jpeg(np.zeros((3000, 4000, 3), np.uint8)), 1600).shape[:2]) == 1600


def test_when_the_file_is_not_an_image_should_raise_bad_image():
    with pytest.raises(BadImage):
        load_bgr(b"not an image", 1600)


def test_when_the_image_is_huge_should_be_a_bad_image_not_a_crash(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)  # Pillow refuses anything over 2x this
    with pytest.raises(BadImage, match="too large"):
        load_bgr(jpeg(np.zeros((300, 400, 3), np.uint8)), 1600)


def test_when_a_jpeg_is_large_should_decode_it_smaller_and_still_rotate_it():
    img = Image.new("RGB", (6000, 3000), "white")
    exif = img.getexif()
    exif[0x0112] = 6
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes())
    assert load_bgr(buf.getvalue(), 1600).shape[:2] == (1600, 800)


def test_when_giving_live_tips_should_return_the_box_in_unit_coordinates(cfg):
    reader, gate = FakeReader(), FakeGate()
    reg = registry(cfg, reader=reader, gate=gate)
    small = cv2.resize(meter_image(), (640, 480))
    f = guide_frame(jpeg(small), reg, cfg)
    assert f.available and f.guidance == [OK] and f.box_method == "window"
    assert f.box == pytest.approx({"x1": 0.25, "y1": 0.4167, "x2": 0.75, "y2": 0.5833}, abs=0.01)
    assert reader.calls == 0  # frames never run the reader


def test_when_a_live_frame_is_dark_should_say_too_dark(cfg):
    dark = (cv2.resize(meter_image(), (640, 480)) * 0.1).astype(np.uint8)
    assert TOO_DARK in guide_frame(jpeg(dark), registry(cfg), cfg).guidance


def test_when_models_are_missing_should_offer_typing_without_claiming_no_meter(cfg):
    reg = registry(cfg, yolo=False)
    reg.reader = None
    r = analyze_photo(jpeg(meter_image()), reg, cfg)
    assert not r.models_ready and r.offer_manual_entry and r.reading_digits is None
    assert NO_METER not in r.guidance


def test_when_model_files_are_missing_should_report_them(tmp_path):
    reg = ModelRegistry().load(tmp_path)
    assert not reg.ready
    assert all(s.state == "missing" for s in reg.status.values())
