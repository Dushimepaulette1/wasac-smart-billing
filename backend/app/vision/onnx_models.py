"""The three models on ONNX Runtime: no PyTorch, torchvision or Ultralytics at serve time.

The .onnx files are exported from the .pt weights by scripts/export_onnx.py, which also checks
that both give the same answers. Pre- and post-processing here repeat what torchvision and
Ultralytics do, step by step:

    YOLO      letterbox to 640 on the long side, padded (grey 114, centred) only up to a
              multiple of 32, as Ultralytics does for .pt models; RGB, /255; the output is
              (1, 4 + classes, anchors) with boxes as centre/size; keep scores > conf, then
              per-class NMS (IoU 0.7, at most 300), then undo the letterbox.
    reader    grayscale, bilinear resize to 64x256, /255, (x - 0.5) / 0.5; CTC greedy decode.
    gate      RGB, bilinear resize to 128x384, /255, ImageNet mean/std; softmax.

Like the .pt files, the .onnx files come from Benax's best.pt and stay private.
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from wasac_preprocessing import digits_to_m3, pad_reading

BLANK = 10
IOU = 0.7
MAX_DET = 300
LETTERBOX_FILL = 114


def _session(path: Path):
    import onnxruntime as ort

    options = ort.SessionOptions()
    # One request at a time on a small CPU: fewer threads, less memory.
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    # No growing memory pool kept between requests: a 512 MB instance has little to spare.
    options.enable_cpu_mem_arena = False
    return ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])


# ---- YOLO ------------------------------------------------------------------


STRIDE = 32


def letterbox(img_bgr: np.ndarray, size: int, auto: bool = True):
    """Ultralytics LetterBox(center=True); auto=True pads only to a multiple of 32 (as for .pt
    models), auto=False to a full size x size square. Returns (image, gain, (pad_x, pad_y))."""
    h, w = img_bgr.shape[:2]
    gain = min(size / h, size / w)
    new_w, new_h = int(round(w * gain)), int(round(h * gain))
    if (new_w, new_h) != (w, h):
        img_bgr = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    dw, dh = size - new_w, size - new_h
    if auto:
        dw, dh = dw % STRIDE, dh % STRIDE
    dw, dh = dw / 2, dh / 2
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    out = cv2.copyMakeBorder(img_bgr, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(LETTERBOX_FILL,) * 3)
    return out, gain, (left, top)


def nms(boxes: np.ndarray, scores: np.ndarray, iou: float) -> np.ndarray:
    """Indices kept by greedy non-maximum suppression, best score first (as torchvision.ops.nms)."""
    order = scores.argsort()[::-1]
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    keep = []
    while order.size:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(boxes[i, 0], boxes[order[1:], 0])
        yy1 = np.maximum(boxes[i, 1], boxes[order[1:], 1])
        xx2 = np.minimum(boxes[i, 2], boxes[order[1:], 2])
        yy2 = np.minimum(boxes[i, 3], boxes[order[1:], 3])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        overlap = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
        order = order[1:][overlap <= iou]
    return np.array(keep, dtype=int)


def postprocess(output: np.ndarray, conf: float, gain: float, pad, orig_shape, max_wh: float = 7680.0):
    """(1, 4 + nc, N) raw YOLOv8 output -> (cls, xyxy, confs) in original image pixels."""
    pred = output[0].T  # (N, 4 + nc)
    class_scores = pred[:, 4:]
    cls = class_scores.argmax(1)
    scores = class_scores[np.arange(len(pred)), cls]
    keep = scores > conf
    if not keep.any():
        return np.zeros(0, dtype=int), np.zeros((0, 4)), np.zeros(0)
    pred, cls, scores = pred[keep], cls[keep], scores[keep]
    cx, cy, bw, bh = pred[:, 0], pred[:, 1], pred[:, 2], pred[:, 3]
    xyxy = np.stack([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], axis=1)
    # Per-class NMS in one pass: shift each class's boxes far apart.
    kept = nms(xyxy + (cls * max_wh)[:, None], scores, IOU)[:MAX_DET]
    xyxy, cls, scores = xyxy[kept], cls[kept], scores[kept]
    xyxy[:, [0, 2]] -= pad[0]
    xyxy[:, [1, 3]] -= pad[1]
    xyxy /= gain
    h, w = orig_shape[:2]
    xyxy[:, [0, 2]] = xyxy[:, [0, 2]].clip(0, w)
    xyxy[:, [1, 3]] = xyxy[:, [1, 3]].clip(0, h)
    return cls.astype(int), xyxy, scores


class OnnxYolo:
    """The cropper. wasac_preprocessing.detect() calls detect_numpy() instead of Ultralytics' predict()."""

    def __init__(self, path: Path):
        self.session = _session(path)
        self.input_name = self.session.get_inputs()[0].name
        # Exported with dynamic height/width (scripts/export_onnx.py); a fixed export is padded square.
        self.fixed = isinstance(self.session.get_inputs()[0].shape[-1], int)

    def detect_numpy(self, img_bgr: np.ndarray, conf: float = 0.15, imgsz: int = 640):
        boxed, gain, pad = letterbox(img_bgr, imgsz, auto=not self.fixed)
        x = np.ascontiguousarray(boxed[:, :, ::-1].transpose(2, 0, 1), dtype=np.float32)[None] / 255.0
        output = self.session.run(None, {self.input_name: x})[0]
        return postprocess(output, conf, gain, pad, img_bgr.shape)


# ---- Reader ----------------------------------------------------------------


def reader_input(image: Image.Image, height: int = 64, width: int = 256) -> np.ndarray:
    """torchvision Grayscale -> Resize((64, 256)) -> ToTensor -> Normalize([0.5], [0.5])."""
    grey = image.convert("RGB").convert("L").resize((width, height), Image.BILINEAR)
    x = np.asarray(grey, dtype=np.float32) / 255.0
    return ((x - 0.5) / 0.5)[None, None]


def decode_with_confidence(log_probs: np.ndarray):
    """CTC greedy decode of (32, 11) log-probs: (digits, mean and lowest probability of the kept digits)."""
    probs = np.exp(log_probs)
    best_i = probs.argmax(-1)
    best_p = probs.max(-1)
    out, conf, prev = [], [], None
    for p, i in zip(best_p, best_i):
        if i != prev and i != BLANK:
            out.append(str(int(i)))
            conf.append(float(p))
        prev = i
    return "".join(out), (sum(conf) / len(conf) if conf else 0.0), (min(conf) if conf else 0.0)


class OnnxReader:
    """Same answers as wasac_models.MeterReader.read()."""

    def __init__(self, path: Path, reader_config: dict):
        self.session = _session(path)
        self.input_name = self.session.get_inputs()[0].name
        self.height, self.width = reader_config.get("input_size", [64, 256])

    def read(self, image):
        if not isinstance(image, Image.Image):
            image = Image.open(image)
        log_probs = self.session.run(None, {self.input_name: reader_input(image, self.height, self.width)})[0][0]
        raw, conf_mean, conf_min = decode_with_confidence(log_probs)
        padded = pad_reading(raw)
        return {
            "raw_digits": raw,
            "reading_digits": padded,
            "reading_m3": digits_to_m3(padded),
            "confidence_mean": round(conf_mean, 4),
            "confidence_min": round(conf_min, 4),
            "needs_check": padded is None,
        }


# ---- Quality gate ----------------------------------------------------------


def gate_input(image: Image.Image, gate_config: dict) -> np.ndarray:
    """torchvision Resize((128, 384)) -> ToTensor -> Normalize(ImageNet mean/std)."""
    h, w = gate_config["input_size"]
    rgb = image.convert("RGB").resize((w, h), Image.BILINEAR)
    x = np.asarray(rgb, dtype=np.float32) / 255.0
    mean = np.array(gate_config["normalize_mean"], dtype=np.float32)
    std = np.array(gate_config["normalize_std"], dtype=np.float32)
    return ((x - mean) / std).transpose(2, 0, 1)[None].astype(np.float32)


class OnnxQualityGate:
    """Same as vision.models.QualityGate: score() is P(unreadable)."""

    def __init__(self, path: Path, gate_config: dict):
        self.session = _session(path)
        self.input_name = self.session.get_inputs()[0].name
        self.gate_config = gate_config
        self.threshold = float(gate_config["threshold"])
        self.unreadable_index = int(gate_config["positive_class_index"])

    def score(self, pil_image) -> float:
        logits = self.session.run(None, {self.input_name: gate_input(pil_image, self.gate_config)})[0][0]
        e = np.exp(logits - logits.max())
        return float((e / e.sum())[self.unreadable_index])
