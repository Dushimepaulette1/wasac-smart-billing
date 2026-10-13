"""Shared preprocessing for the WASAC meter pipeline (training notebook and FastAPI backend)."""
import numpy as np

DISPLAY_CLASS = 1                       # YOLO class id of the meter display window
DIGIT_CLASSES = set(range(2, 12))       # YOLO class ids 2..11 are the digits 0..9
READING_LENGTH = 8                      # 5 cubic-metre wheels + 3 litre wheels
DECIMALS = 3


def detect(img_bgr, yolo_model, conf=0.15, imgsz=640, device=None):
    """Run YOLO once. Returns (cls, xyxy, confs) as numpy arrays (empty arrays when nothing is found)."""
    result = yolo_model.predict(source=img_bgr, imgsz=imgsz, conf=conf, device=device, verbose=False)[0]
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return np.zeros(0, dtype=int), np.zeros((0, 4)), np.zeros(0)
    return boxes.cls.cpu().numpy().astype(int), boxes.xyxy.cpu().numpy(), boxes.conf.cpu().numpy()


def display_box(cls, xyxy, confs, w, h):
    """The number window's box from detections: (x1, y1, x2, y2, method), unpadded.

    method is 'window' (best window box), 'digits' (union of digit boxes), 'full' (other
    detections only: the whole image) or 'none' (nothing detected).
    """
    if len(cls) == 0:
        return None, "none"
    windows = [i for i, c in enumerate(cls) if c == DISPLAY_CLASS]
    if windows:
        best = max(windows, key=lambda i: confs[i])
        x1, y1, x2, y2 = map(int, xyxy[best])
        return (x1, y1, x2, y2), "window"
    digits = [xyxy[i] for i, c in enumerate(cls) if c in DIGIT_CLASSES]
    if digits:
        x1 = int(min(b[0] for b in digits)); y1 = int(min(b[1] for b in digits))
        x2 = int(max(b[2] for b in digits)); y2 = int(max(b[3] for b in digits))
        return (x1, y1, x2, y2), "digits"
    return (0, 0, w, h), "full"


def crop_box(img_bgr, box, pad=0.05):
    """Crop a box with padding, clipped to the image. Returns None for an empty crop."""
    h, w = img_bgr.shape[:2]
    x1, y1, x2, y2 = box
    px, py = int((x2 - x1) * pad), int((y2 - y1) * pad)
    x1, y1 = max(0, x1 - px), max(0, y1 - py)
    x2, y2 = min(w, x2 + px), min(h, y2 + py)
    crop = img_bgr[y1:y2, x1:x2]
    return None if crop.size == 0 else crop


def crop_display(img_bgr, yolo_model, conf=0.15, imgsz=640, device=None, pad=0.05):
    """Cut the number window out of a full meter photo.

    Returns (crop_bgr, method) where method is 'window', 'digits', 'full' or 'none'.
    """
    h, w = img_bgr.shape[:2]
    box, method = display_box(*detect(img_bgr, yolo_model, conf, imgsz, device), w, h)
    if box is None:
        return None, "none"
    crop = crop_box(img_bgr, box, pad)
    return (None, "none") if crop is None else (crop, method)


def pad_reading(digits, length=READING_LENGTH):
    """Add the leading zeros the reader sometimes drops: '565846' -> '00565846'.

    Returns None when the reading has more digits than the meter has wheels,
    so the app can ask the household to check the numbers instead of guessing.
    """
    digits = "".join(ch for ch in str(digits) if ch.isdigit())
    if not digits or len(digits) > length:
        return None
    return digits.zfill(length)


def digits_to_m3(padded_digits, decimals=DECIMALS):
    """'00565846' -> 565.846 cubic metres."""
    if padded_digits is None:
        return None
    return int(padded_digits[:-decimals]) + int(padded_digits[-decimals:]) / 10 ** decimals
