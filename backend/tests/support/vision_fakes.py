"""Fake YOLO, reader and quality gate, and synthetic meter photos, for vision tests without real weights."""
import cv2
import numpy as np
from app.vision.models import ModelRegistry
from app.vision.pipeline import analyze_photo

W, H = 1600, 1200


WINDOW = (400, 500, 1200, 700)  # a clearly visible number window, well inside the frame


WINDOW_CLS, DIGIT_CLS = 1, 2


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


def registry(cfg, dets=((WINDOW_CLS, WINDOW, 0.9),), reader=None, gate=None, yolo=True):
    reg = ModelRegistry()
    reg.guidance = cfg
    reg.yolo = FakeYolo(list(dets)) if yolo else None
    reg.reader = reader if reader is not None else FakeReader()
    reg.quality_gate = gate if gate is not None else FakeGate()
    return reg


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
