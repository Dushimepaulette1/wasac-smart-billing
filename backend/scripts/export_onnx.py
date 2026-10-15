"""Export the three .pt models to ONNX and check both give the same answers.

    python scripts/export_onnx.py                 # writes ml/best.onnx, ml/meter_reader.onnx, ml/quality_gate.onnx
    python scripts/export_onnx.py --check-only    # compare existing .onnx files with the .pt ones
    python scripts/export_onnx.py --images DIR    # also compare on real photos (e.g. calibration/)

Needs torch, torchvision and ultralytics (training environment); serving then needs only
onnxruntime (requirements-serve.txt). The .onnx files are derived from Benax's best.pt and our own
weights: like the .pt files they are private, never committed (.gitignore) and never put in an image
(.dockerignore). Their checksums are written to ml/weights.sha256.json for scripts/download_models.py.

Prints, per model, the largest output difference and how often the decisions differ.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "ml"))

from vision.config import load_model_config, weights_dir, yolo_weights_name  # noqa: E402

OPSET = 17


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def export_yolo(pt: Path) -> Path:
    from ultralytics import YOLO

    # dynamic: any height/width, so photos are padded only to a multiple of 32, as for the .pt model.
    out = YOLO(str(pt)).export(format="onnx", imgsz=640, opset=OPSET, dynamic=True, simplify=False, verbose=False)
    return Path(out)


def export_reader(pt: Path, arch: str) -> Path:
    import torch
    from wasac_models import build_model

    model = build_model(arch)
    model.load_state_dict(torch.load(pt, map_location="cpu"))
    model.eval()
    out = pt.with_suffix(".onnx")
    torch.onnx.export(model, torch.zeros(1, 1, 64, 256), str(out), opset_version=OPSET,
                      input_names=["image"], output_names=["log_probs"])
    return out


def export_gate(pt: Path, gate_cfg: dict) -> Path:
    import torch
    import torchvision

    model = torchvision.models.mobilenet_v2(weights=None)
    model.classifier[1] = torch.nn.Linear(model.last_channel, 2)
    model.load_state_dict(torch.load(pt, map_location="cpu"))
    model.eval()
    h, w = gate_cfg["input_size"]
    out = pt.with_suffix(".onnx")
    torch.onnx.export(model, torch.zeros(1, 3, h, w), str(out), opset_version=OPSET,
                      input_names=["image"], output_names=["logits"])
    return out


def test_images(extra_dir, limit=None):
    """Synthetic meter-like pictures, plus real photos if a folder is given."""
    import cv2

    rng = np.random.default_rng(0)
    images = []
    for i in range(12):
        h, w = [(480, 640), (1080, 1920), (1600, 1200), (720, 720)][i % 4]
        img = np.full((h, w, 3), rng.integers(60, 200), np.uint8)
        x, y = w // 4, h // 3
        cv2.rectangle(img, (x, y), (3 * w // 4, y + h // 6), (20, 20, 20), -1)
        for d in range(8):
            cv2.putText(img, str(rng.integers(0, 10)), (x + 10 + d * (w // 18), y + h // 8),
                        cv2.FONT_HERSHEY_SIMPLEX, h / 400, (230, 230, 230), 3)
        images.append(("synthetic", img))
    if extra_dir:
        paths = [p for p in sorted(Path(extra_dir).rglob("*")) if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
        if limit and len(paths) > limit:
            paths = [paths[i] for i in np.linspace(0, len(paths) - 1, limit).astype(int)]  # spread evenly
        for p in paths:
            img = cv2.imread(str(p))
            if img is not None:
                images.append(("photo", img))
    return images


def compare(directory: Path, cfg: dict, extra_dir, limit=None) -> bool:
    import cv2
    from PIL import Image
    from ultralytics import YOLO

    from vision.models import QualityGate
    from vision.onnx_models import OnnxQualityGate, OnnxReader, OnnxYolo
    from wasac_models import MeterReader
    from wasac_preprocessing import crop_display, detect

    yolo_pt = YOLO(str(directory / yolo_weights_name(cfg)))
    yolo_onnx = OnnxYolo(directory / Path(yolo_weights_name(cfg)).with_suffix(".onnx"))
    reader_pt = MeterReader(str(directory / cfg["reader"]["weights"]), arch=cfg["reader"]["arch"])
    reader_onnx = OnnxReader(directory / Path(cfg["reader"]["weights"]).with_suffix(".onnx"), cfg["reader"])
    gate_pt = QualityGate(directory / cfg["quality_gate"]["weights"], cfg["quality_gate"])
    gate_onnx = OnnxQualityGate(directory / Path(cfg["quality_gate"]["weights"]).with_suffix(".onnx"), cfg["quality_gate"])
    conf, imgsz, pad = cfg["cropper"]["conf"], cfg["cropper"]["imgsz"], cfg["cropper"]["padding"]

    images = test_images(extra_dir, limit)
    det_count_diff = box_diff = 0.0
    det_mismatch = read_mismatch = gate_flip = 0
    gate_diff = 0.0
    for _, img in images:
        c1, b1, s1 = detect(img, yolo_pt, conf, imgsz, "cpu")
        c2, b2, s2 = detect(img, yolo_onnx, conf, imgsz, "cpu")
        if len(c1) != len(c2) or sorted(c1.tolist()) != sorted(c2.tolist()):
            det_mismatch += 1
        elif len(b1):
            o1, o2 = np.lexsort(b1.T[::-1]), np.lexsort(b2.T[::-1])
            box_diff = max(box_diff, float(np.abs(b1[o1] - b2[o2]).max()))
        det_count_diff = max(det_count_diff, abs(len(c1) - len(c2)))
        crop, _ = crop_display(img, yolo_onnx, conf, imgsz, "cpu", pad)
        crop = img if crop is None else crop
        pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        r1, r2 = reader_pt.read(pil), reader_onnx.read(pil)
        read_mismatch += r1["raw_digits"] != r2["raw_digits"]
        g1, g2 = gate_pt.score(pil), gate_onnx.score(pil)
        gate_diff = max(gate_diff, abs(g1 - g2))
        gate_flip += (g1 >= gate_pt.threshold) != (g2 >= gate_onnx.threshold)

    n = len(images)
    print(f"Compared on {n} images ({sum(k == 'photo' for k, _ in images)} real photos)")
    print(f"  YOLO:   detections differ on {det_mismatch}/{n}; largest box difference {box_diff:.2f} px")
    print(f"  reader: digits differ on {read_mismatch}/{n}")
    print(f"  gate:   largest score difference {gate_diff:.5f}; retake decision differs on {gate_flip}/{n}")
    return det_mismatch == 0 and read_mismatch == 0 and gate_flip == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", type=Path, default=None, help="Weights folder (default: ML_WEIGHTS_DIR or backend/ml)")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--images", type=Path, default=None, help="Folder of real meter photos to compare on")
    parser.add_argument("--limit", type=int, default=150, help="At most this many photos, spread evenly")
    args = parser.parse_args()

    directory = args.dir or weights_dir()
    cfg = load_model_config()
    if not args.check_only:
        outputs = [
            export_yolo(directory / yolo_weights_name(cfg)),
            export_reader(directory / cfg["reader"]["weights"], cfg["reader"]["arch"]),
            export_gate(directory / cfg["quality_gate"]["weights"], cfg["quality_gate"]),
        ]
        sums_path = BACKEND / "ml" / "weights.sha256.json"
        sums = json.loads(sums_path.read_text())
        for out in outputs:
            sums[out.name] = {"sha256": sha256(out), "bytes": out.stat().st_size}
            print(f"Wrote {out.name} ({out.stat().st_size / 1e6:.1f} MB)")
        sums_path.write_text(json.dumps(sums, indent=2) + "\n")
    same = compare(directory, cfg, args.images, args.limit)
    print("Same answers." if same else "Some answers differ: see above before switching to ONNX.")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
