"""Calibrate photo-guidance thresholds on real photos.

    python scripts/calibrate_guidance.py --meters PATH --non-meters PATH [--csv out.csv]
    python scripts/calibrate_guidance.py --from-csv out.csv          # re-score saved measurements, no models

For every photo it measures what the guidance checks look at (window confidence, digit boxes, window
size and position, brightness, glare, blur, quality-gate score, reader confidence). It then prints
how often each code fires on meter photos and on non-meter photos with the thresholds in
vision/guidance_config.json, and sweeps each threshold so you can pick values. The reader and gate
are run on every crop, even when NO_METER would skip them in the API, so the sweeps are complete.
"""
import argparse
import csv
import dataclasses
import sys
import time
from pathlib import Path
from statistics import median
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vision  # noqa: E402,F401
from vision.config import GuidanceConfig, load_model_config  # noqa: E402
from vision.guidance import Measurements, guidance_codes  # noqa: E402
from vision.image_io import BadImage, bgr_to_pil, load_bgr  # noqa: E402
from vision.pipeline import _locate  # noqa: E402

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
CODES = ["NO_METER", "TOO_FAR", "CUT_OFF", "TOO_DARK", "GLARE", "BLURRY", "HARD_TO_READ", "CHECK_NUMBERS", "OK"]
FIELDS = [f.name for f in dataclasses.fields(Measurements)]


def images_in(folder: Path) -> List[Path]:
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in IMAGE_EXT)


def measure(path: Path, registry, cfg) -> dict:
    start = time.perf_counter()
    img = load_bgr(path.read_bytes(), cfg.max_long_side)
    m, crop = _locate(img, registry, cfg, cfg.yolo_imgsz)
    if crop is not None:
        pil = bgr_to_pil(crop)
        if registry.quality_gate is not None:
            m.quality_score = round(registry.quality_gate.score(pil), 4)
        read = registry.reader.read(pil)
        m.confidence_min, m.needs_check = read["confidence_min"], read["needs_check"]
    row = m.to_dict()
    row["box"] = "" if m.box is None else " ".join(map(str, m.box))
    row["seconds"] = round(time.perf_counter() - start, 3)
    return row


def to_measurements(row: dict) -> Measurements:
    def num(v, cast=float):
        return None if v in ("", None, "None") else cast(v)

    box = tuple(int(v) for v in row["box"].split()) if row.get("box") else None
    return Measurements(
        image_w=int(row["image_w"]), image_h=int(row["image_h"]), window_conf=float(row["window_conf"]),
        digit_boxes=int(row["digit_boxes"]), box=box, box_method=row["box_method"],
        region_mean=float(row["region_mean"]), glare_frac=float(row["glare_frac"]),
        laplacian_var=float(row["laplacian_var"]), quality_score=num(row["quality_score"]),
        confidence_min=num(row["confidence_min"]),
        needs_check=None if row["needs_check"] in ("", "None") else str(row["needs_check"]) == "True",
    )


def rates(rows: List[dict], cfg: GuidanceConfig) -> Dict[str, float]:
    counts = {c: 0 for c in CODES}
    for row in rows:
        for code in guidance_codes(to_measurements(row), cfg):
            counts[code] += 1
    return {c: (100.0 * n / len(rows) if rows else 0.0) for c, n in counts.items()}


def pct(values, q):
    values = sorted(v for v in values if v is not None)
    return values[min(len(values) - 1, int(q * len(values)))] if values else None


SWEEPS = {
    "NO_METER": ("no_meter_window_conf", [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]),
    "TOO_FAR": ("too_far_min_width_frac", [0.1, 0.15, 0.2, 0.25, 0.3]),
    "CUT_OFF": ("cut_off_edge_frac", [0.0, 0.005, 0.01, 0.02]),
    "TOO_DARK": ("too_dark_max_mean", [30, 45, 60, 75, 90]),
    "GLARE": ("glare_max_frac", [0.01, 0.02, 0.05, 0.1, 0.2]),
    "BLURRY": ("blurry_max_laplacian_var", [20, 40, 60, 80, 120, 200, 400]),
    "HARD_TO_READ": ("hard_to_read_threshold", [0.3, 0.4, 0.43, 0.5, 0.6, 0.7]),
    "CHECK_NUMBERS": ("check_numbers_min_confidence", [0.4, 0.5, 0.6, 0.7, 0.8]),
}


def report(meters: List[dict], others: List[dict], cfg: GuidanceConfig) -> None:
    print(f"\nPhotos: {len(meters)} meter, {len(others)} non-meter")
    print("\nHow often each code fires with the current thresholds (vision/guidance_config.json):")
    rm, ro = rates(meters, cfg), rates(others, cfg)
    print(f"  {'code':<15}{'meter photos':>14}{'non-meter':>12}")
    for c in CODES:
        print(f"  {c:<15}{rm[c]:>13.1f}%{ro[c]:>11.1f}%")

    print("\nMeasurement percentiles on METER photos (p5 / p25 / p50 / p75 / p95):")
    for key in ("window_conf", "digit_boxes", "region_mean", "glare_frac", "laplacian_var",
                "quality_score", "confidence_min"):
        vals = [None if r[key] in ("", None, "None") else float(r[key]) for r in meters]
        qs = [pct(vals, q) for q in (0.05, 0.25, 0.5, 0.75, 0.95)]
        print(f"  {key:<16}" + " / ".join("-" if v is None else f"{v:.3g}" for v in qs))

    print("\nThreshold sweeps: % of meter photos / % of non-meter photos where the code fires")
    for code, (attr, candidates) in SWEEPS.items():
        cells = []
        for value in candidates:
            variant = dataclasses.replace(cfg, **{attr: value})
            cells.append(f"{value}: {rates(meters, variant)[code]:.0f}/{rates(others, variant)[code]:.0f}")
        current = getattr(cfg, attr)
        print(f"  {code:<14}({attr}, now {current})\n      " + "   ".join(cells))

    scores = [float(r["quality_score"]) for r in meters if r["quality_score"] not in ("", None, "None")]
    if scores:
        med = median(scores)
        print(f"\nQuality gate check: median P(unreadable) on meter photos = {med:.3f}"
              f" (threshold {cfg.hard_to_read_threshold:.3f}).")
        if med >= cfg.hard_to_read_threshold:
            print("  WARNING: most real meter photos score as unreadable. The class index in"
                  " vision/models.py (QUALITY_GATE_UNREADABLE_INDEX) may be the wrong way round.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--meters", type=Path, help="Folder of real meter photos")
    parser.add_argument("--non-meters", type=Path, help="Folder of photos that are not meters")
    parser.add_argument("--csv", type=Path, help="Save per-photo measurements here")
    parser.add_argument("--from-csv", type=Path, help="Re-score a saved CSV with the current thresholds")
    args = parser.parse_args()

    cfg = GuidanceConfig.load(quality_threshold=load_model_config()["quality_gate"]["threshold"])
    if args.from_csv:
        with open(args.from_csv, newline="") as f:
            rows = list(csv.DictReader(f))
        report([r for r in rows if r["group"] == "meter"], [r for r in rows if r["group"] == "non_meter"], cfg)
        return
    if not (args.meters and args.non_meters):
        parser.error("give --meters and --non-meters, or --from-csv")

    from vision.models import ModelRegistry

    registry = ModelRegistry().load()
    if not registry.ready:
        sys.exit(f"Models not loaded: {registry.health()}. Run scripts/download_models.py first.")

    rows = []
    for group, folder in (("meter", args.meters), ("non_meter", args.non_meters)):
        paths = images_in(folder)
        print(f"{group}: {len(paths)} photos in {folder}")
        for i, path in enumerate(paths, 1):
            try:
                row = measure(path, registry, cfg)
            except BadImage as e:
                print(f"  skipped {path.name}: {e}")
                continue
            row.update(group=group, file=str(path.relative_to(folder)))
            rows.append(row)
            print(f"\r  {i}/{len(paths)}", end="", flush=True)
        print()

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["group", "file", *FIELDS, "seconds"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"Saved measurements to {args.csv}")

    secs = [r["seconds"] for r in rows]
    if secs:
        print(f"Time per photo (measure + gate + reader, CPU): median {median(secs):.2f}s, max {max(secs):.2f}s")
    report([r for r in rows if r["group"] == "meter"], [r for r in rows if r["group"] == "non_meter"], cfg)


if __name__ == "__main__":
    main()
