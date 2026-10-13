"""CPU time per photo and per guide-frame, and peak memory with all three models loaded.

    python scripts/benchmark_vision.py                     # synthetic inputs, per stage
    python scripts/benchmark_vision.py --photos PATH       # real photos, end to end

Timings are measured warm (after one untimed call), as the API serves them after start-up.
"""
import argparse
import resource
import sys
import time
from pathlib import Path
from statistics import median

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vision  # noqa: E402,F401
from vision.image_io import bgr_to_pil  # noqa: E402
from vision.pipeline import analyze_photo, guide_frame  # noqa: E402
from wasac_preprocessing import detect  # noqa: E402


def peak_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # Linux reports KB


def timed(fn, runs):
    fn()  # warm-up
    out = []
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t) * 1000)
    return median(out), max(out)


def jpeg(img, quality=85):
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])[1].tobytes()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--photos", type=Path)
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()

    import torch

    print(f"torch threads: {torch.get_num_threads()}   peak memory before models: {peak_mb():.0f} MB")
    t = time.perf_counter()
    from vision.models import ModelRegistry

    reg = ModelRegistry().load()
    print(f"Model load (imports + weights + warm-up): {time.perf_counter() - t:.1f}s   {reg.health()}")
    print(f"Peak memory with all three models loaded: {peak_mb():.0f} MB")
    cfg = reg.guidance_config()

    if args.photos:
        paths = sorted(p for p in args.photos.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
        photo_ms, frame_ms = [], []
        for p in paths[:1]:
            analyze_photo(p.read_bytes(), reg, cfg)
        for p in paths:
            data = p.read_bytes()
            t = time.perf_counter()
            analyze_photo(data, reg, cfg)
            photo_ms.append((time.perf_counter() - t) * 1000)
            img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            s = 640 / max(img.shape[:2])
            small = jpeg(cv2.resize(img, (round(img.shape[1] * s), round(img.shape[0] * s))), 70)
            t = time.perf_counter()
            guide_frame(small, reg, cfg)
            frame_ms.append((time.perf_counter() - t) * 1000)
        print(f"\n{len(paths)} real photos")
        print(f"  /submit-photo pipeline: median {median(photo_ms):.0f} ms, max {max(photo_ms):.0f} ms")
        print(f"  /guide-frame (640 px):  median {median(frame_ms):.0f} ms, max {max(frame_ms):.0f} ms")
    else:
        photo = np.random.default_rng(0).integers(0, 255, (1200, 1600, 3), dtype=np.uint8)
        photo = cv2.GaussianBlur(photo, (0, 0), 3)
        crop = np.full((180, 640, 3), 235, np.uint8)
        for x in range(10, 630, 40):
            crop[30:-30, x:x + 14] = 15
        pil_crop = bgr_to_pil(crop)
        photo_jpeg, frame_jpeg = jpeg(photo), jpeg(cv2.resize(photo, (640, 480)), 70)
        from vision.image_io import load_bgr

        stages = {
            "decode + EXIF + resize (1600 px)": lambda: load_bgr(photo_jpeg, cfg.max_long_side),
            "YOLO at imgsz 640 (1600 px photo)": lambda: detect(photo, reg.yolo, cfg.yolo_conf, cfg.yolo_imgsz, "cpu"),
            "quality gate on a crop": lambda: reg.quality_gate.score(pil_crop),
            "reader on a crop": lambda: reg.reader.read(pil_crop),
            "whole /guide-frame (640 px JPEG)": lambda: guide_frame(frame_jpeg, reg, cfg),
        }
        print(f"\nSynthetic inputs, {args.runs} warm runs each (median / max):")
        totals = {}
        for name, fn in stages.items():
            med, mx = timed(fn, args.runs)
            totals[name] = med
            print(f"  {name:<36} {med:7.0f} ms / {mx:5.0f} ms")
        est = sum(v for k, v in totals.items() if "guide-frame" not in k)
        print(f"  {'=> /submit-photo estimate':<36} {est:7.0f} ms (decode + YOLO + gate + reader)")
    print(f"\nPeak memory at the end: {peak_mb():.0f} MB")


if __name__ == "__main__":
    main()
