"""Cut "not a meter" background patches from meter photos, for calibrating NO_METER.

    python scripts/make_background_patches.py --photos calibration/meters-all/images \
        --out calibration/not_meters_auto

For each photo where YOLO finds the number window, up to --per-photo patches are cut from regions
that stay clear of the window (window box grown by --margin of the photo size on every side). Each
patch is --size of the photo's width and height (at least 30%). They show what the camera sees when
it is not pointed at the meter: pipes, soil, walls, the meter box.
"""
import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app.vision  # noqa: F401  puts backend/ml on sys.path
from app.vision.image_io import BadImage, load_bgr  # noqa: E402
from wasac_preprocessing import detect, display_box  # noqa: E402

IMAGE_EXT = {".jpg", ".jpeg", ".png"}


def overlaps(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def patches_for(w, h, box, size, margin, per_photo):
    pw, ph = int(w * size), int(h * size)
    mx, my = int(w * margin), int(h * margin)
    keep_out = (box[0] - mx, box[1] - my, box[2] + mx, box[3] + my)
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    candidates = [(x, y, x + pw, y + ph) for x in (0, (w - pw) // 2, w - pw) for y in (0, (h - ph) // 2, h - ph)]
    candidates = [c for c in candidates if not overlaps(c, keep_out)]
    candidates.sort(key=lambda c: -((c[0] + c[2]) / 2 - cx) ** 2 - ((c[1] + c[3]) / 2 - cy) ** 2)
    chosen = []
    for c in candidates:  # farthest from the window first, and not overlapping each other
        if all(not overlaps(c, o) for o in chosen):
            chosen.append(c)
        if len(chosen) == per_photo:
            break
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--photos", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--per-photo", type=int, default=2)
    parser.add_argument("--size", type=float, default=0.35, help="Patch width/height as a share of the photo")
    parser.add_argument("--margin", type=float, default=0.08, help="Clearance around the window box")
    args = parser.parse_args()
    if args.size < 0.3:
        parser.error("--size must be at least 0.3")

    from app.vision.models import ModelRegistry

    reg = ModelRegistry().load()
    if reg.yolo is None:
        sys.exit(f"YOLO not loaded: {reg.health()}")
    cfg = reg.guidance_config()
    args.out.mkdir(parents=True, exist_ok=True)

    photos = sorted(p for p in args.photos.iterdir() if p.suffix.lower() in IMAGE_EXT)
    no_window = written = 0
    for i, path in enumerate(photos, 1):
        try:
            img = load_bgr(path.read_bytes(), cfg.max_long_side)
        except BadImage:
            continue
        h, w = img.shape[:2]
        box, method = display_box(*detect(img, reg.yolo, cfg.yolo_conf, cfg.yolo_imgsz, "cpu"), w, h)
        if method != "window":
            no_window += 1
            continue
        for k, (x1, y1, x2, y2) in enumerate(patches_for(w, h, box, args.size, args.margin, args.per_photo), 1):
            cv2.imwrite(str(args.out / f"{path.stem}_bg{k}.jpg"), img[y1:y2, x1:x2], [cv2.IMWRITE_JPEG_QUALITY, 90])
            written += 1
        print(f"\r  {i}/{len(photos)} photos, {written} patches", end="", flush=True)
    print(f"\nWrote {written} patches to {args.out}; {no_window} photos had no window detected (skipped).")


if __name__ == "__main__":
    main()
