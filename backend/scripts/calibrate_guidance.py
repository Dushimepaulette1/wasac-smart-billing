"""Calibrate photo-guidance thresholds on labelled WASAC meter photos and non-meter images.

Measure (slow, runs the models once per image and size; writes a CSV of numbers):

    python scripts/calibrate_guidance.py measure \
        --photos calibration/meters-all/images \
        --readable-csv calibration/rwanda_crnn_training_labels.csv \
        --unreadable-csv calibration/rwanda_unreadable_labels.csv \
        --non-meter patches=calibration/not_meters_auto --non-meter coco=calibration/not_meters_coco \
        --sizes 640 416 320 --csv calibration/guidance_measurements.csv

Report (fast, no models; re-scores the CSV with vision/guidance_config.json and suggests thresholds):

    python scripts/calibrate_guidance.py report --csv calibration/guidance_measurements.csv \
        [--markdown ../docs/calibration/guidance_calibration.md]

Each image is measured as /submit-photo sees it ("photo": long side 1600 px, YOLO at 640, quality
gate and reader on the crop) and as /guide-frame sees it ("frame": a 640 px JPEG, YOLO at each
--sizes value, brightness/glare/blur only). The gate and reader run on every crop, even where
NO_METER would skip them, so the sweeps are complete. Meter photos are grouped with the label CSVs
by original_filename: readable, unreadable, or unlabelled (used only for the NO_METER check).
"""
import argparse
import csv
import dataclasses
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Dict, List, Optional, Sequence

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vision  # noqa: E402,F401
from vision.config import GuidanceConfig, load_model_config  # noqa: E402
from vision.guidance import Measurements, guidance_codes  # noqa: E402
from vision.image_io import BadImage, bgr_to_pil, load_bgr  # noqa: E402
from vision.pipeline import _locate  # noqa: E402

IMAGE_EXT = {".jpg", ".jpeg", ".png"}
METER_GROUPS = ["readable", "unreadable", "unlabelled"]
FRAME_CODES = ["NO_METER", "TOO_FAR", "CUT_OFF", "TOO_DARK", "GLARE", "BLURRY", "OK"]
PHOTO_CODES = FRAME_CODES[:-1] + ["HARD_TO_READ", "CHECK_NUMBERS", "OK"]
FIELDS = [f.name for f in dataclasses.fields(Measurements)]
TARGET_METERS_KEPT = 97.0     # NO_METER may wrongly fire on at most 3% of real meter photos
MAX_READABLE_NAG = 10.0       # a check may fire on at most ~10% of readable photos
MIN_GAP = 10.0                # ...and must fire at least 10 points more often on unreadable ones

SWEEPS = {  # code -> (config field, candidate values)
    "TOO_FAR": ("too_far_min_width_frac", [0.05, 0.08, 0.1, 0.12, 0.15, 0.2, 0.25, 0.3]),
    "CUT_OFF": ("cut_off_edge_frac", [0.0, 0.002, 0.005, 0.01, 0.02, 0.03]),
    "TOO_DARK": ("too_dark_max_mean", [20, 30, 40, 50, 60, 70, 80, 90, 100]),
    "GLARE": ("glare_max_frac", [0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.1, 0.15, 0.2, 0.3]),
    "BLURRY": ("blurry_max_laplacian_var", [5, 10, 20, 30, 40, 60, 80, 100, 150, 200, 300, 500]),
    "HARD_TO_READ": ("hard_to_read_threshold", [0.2, 0.3, 0.35, 0.4, 0.43, 0.5, 0.6, 0.7, 0.8, 0.9]),
    "CHECK_NUMBERS": ("check_numbers_min_confidence", [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]),
}
NO_METER_CANDIDATES = [round(0.05 * i, 2) for i in range(1, 19)]


# --- measuring ------------------------------------------------------------------

def label_groups(readable_csv: Path, unreadable_csv: Path) -> Dict[str, str]:
    groups = {}
    for path, group in ((readable_csv, "readable"), (unreadable_csv, "unreadable")):
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                groups[row["original_filename"]] = group
    return groups


def measure_image(data: bytes, registry, cfg: GuidanceConfig, sizes: Sequence[int]) -> List[dict]:
    rows = []
    start = time.perf_counter()
    img = load_bgr(data, cfg.max_long_side)
    m, crop = _locate(img, registry, cfg, cfg.yolo_imgsz)
    if crop is not None:
        pil = bgr_to_pil(crop)
        m.quality_score = round(registry.quality_gate.score(pil), 4)
        read = registry.reader.read(pil)
        m.confidence_min, m.needs_check = read["confidence_min"], read["needs_check"]
    rows.append(dict(m.to_dict(), mode="photo", imgsz=cfg.yolo_imgsz, ms=(time.perf_counter() - start) * 1000))

    h, w = img.shape[:2]
    s = cfg.guide_max_long_side / max(h, w)
    small = cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else img
    frame_jpeg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()
    for size in sizes:
        start = time.perf_counter()
        frame = load_bgr(frame_jpeg, cfg.guide_max_long_side)
        fm, _ = _locate(frame, registry, cfg, size)
        rows.append(dict(fm.to_dict(), mode="frame", imgsz=size, ms=(time.perf_counter() - start) * 1000))
    return rows


def run_measure(args) -> None:
    from vision.models import ModelRegistry

    registry = ModelRegistry().load()
    if not registry.ready or registry.quality_gate is None:
        sys.exit(f"Models not loaded: {registry.health()}. Run scripts/download_models.py first.")
    cfg = registry.guidance_config()
    labels = label_groups(args.readable_csv, args.unreadable_csv)

    jobs = [(labels.get(p.name, "unlabelled"), p) for p in sorted(args.photos.iterdir())
            if p.suffix.lower() in IMAGE_EXT]
    for spec in args.non_meter:
        name, folder = spec.split("=", 1)
        jobs += [(name, p) for p in sorted(Path(folder).iterdir()) if p.suffix.lower() in IMAGE_EXT]
    if args.limit:
        jobs = jobs[:args.limit]

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with open(args.csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["group", "file", "mode", "imgsz", *FIELDS, "ms"])
        writer.writeheader()
        for i, (group, path) in enumerate(jobs, 1):
            try:
                rows = measure_image(path.read_bytes(), registry, cfg, args.sizes)
            except BadImage as e:
                print(f"\n  skipped {path.name}: {e}")
                continue
            for row in rows:
                row["box"] = "" if row["box"] is None else " ".join(map(str, row["box"]))
                writer.writerow(dict(row, group=group, file=path.name))
            f.flush()
            print(f"\r  {i}/{len(jobs)} images", end="", flush=True)
    print(f"\nSaved measurements to {args.csv}")


# --- scoring ----------------------------------------------------------------------

def to_measurements(row: dict) -> Measurements:
    def opt(v):
        return None if v in ("", "None", None) else float(v)

    return Measurements(
        image_w=int(row["image_w"]), image_h=int(row["image_h"]), window_conf=float(row["window_conf"]),
        digit_boxes=int(row["digit_boxes"]),
        box=tuple(int(v) for v in row["box"].split()) if row["box"] else None,
        box_method=row["box_method"], region_mean=float(row["region_mean"]),
        glare_frac=float(row["glare_frac"]), laplacian_var=float(row["laplacian_var"]),
        quality_score=opt(row["quality_score"]), confidence_min=opt(row["confidence_min"]),
        needs_check=None if row["needs_check"] in ("", "None") else row["needs_check"] == "True",
    )


class Data:
    def __init__(self, csv_path: Path):
        with open(csv_path, newline="") as f:
            rows = list(csv.DictReader(f))
        self.by: Dict[tuple, List[Measurements]] = defaultdict(list)
        self.ms: Dict[tuple, List[float]] = defaultdict(list)
        self.groups: List[str] = []
        for row in rows:
            key = (row["mode"], int(row["imgsz"]), row["group"])
            self.by[key].append(to_measurements(row))
            self.ms[(row["mode"], int(row["imgsz"]))].append(float(row["ms"]))
            if row["group"] not in self.groups:
                self.groups.append(row["group"])
        self.groups.sort(key=lambda g: (METER_GROUPS + [g]).index(g))
        self.sizes = sorted({k[1] for k in self.by if k[0] == "frame"}, reverse=True)
        self.photo_size = next(k[1] for k in self.by if k[0] == "photo")
        self.non_meter = [g for g in self.groups if g not in METER_GROUPS]

    def items(self, mode, size, groups) -> List[Measurements]:
        return [m for g in groups for m in self.by.get((mode, size, g), [])]

    def count(self, group) -> int:
        return len(self.by.get(("photo", self.photo_size, group), []))


def fire_rate(ms: List[Measurements], cfg: GuidanceConfig, code: str) -> Optional[float]:
    if not ms:
        return None
    return 100.0 * sum(code in guidance_codes(m, cfg) for m in ms) / len(ms)


def fmt(v: Optional[float]) -> str:
    return "–" if v is None else f"{v:.1f}%"


# --- choosing thresholds ------------------------------------------------------------

def choose_no_meter(data: Data, cfg: GuidanceConfig, mode: str, size: int) -> Optional[float]:
    """Largest window-confidence threshold that still keeps >= 97% of readable+unreadable photos."""
    meters = data.items(mode, size, ["readable", "unreadable"])
    best = None
    for c in NO_METER_CANDIDATES:
        kept = 100 - fire_rate(meters, dataclasses.replace(cfg, no_meter_window_conf=c), "NO_METER")
        if kept >= TARGET_METERS_KEPT:
            best = c
    return best


def choose_check(data: Data, cfg: GuidanceConfig, code: str):
    """Best threshold firing on <= ~10% of readable photos and >= 10 points more on unreadable ones."""
    attr, candidates = SWEEPS[code]
    readable = data.items("photo", data.photo_size, ["readable"])
    unreadable = data.items("photo", data.photo_size, ["unreadable"])
    table, best = [], None
    for v in candidates:
        variant = dataclasses.replace(cfg, **{attr: v})
        r, u = fire_rate(readable, variant, code), fire_rate(unreadable, variant, code)
        table.append((v, r, u))
        if r <= MAX_READABLE_NAG and u - r >= MIN_GAP and (best is None or u - r > best[2] - best[1]):
            best = (v, r, u)
    return attr, table, best


# --- report -------------------------------------------------------------------------

def rates_table(data: Data, cfg: GuidanceConfig, mode: str, size: int, codes: List[str]) -> List[str]:
    head = "| Code | " + " | ".join(data.groups) + " |"
    lines = [head, "|---|" + "---|" * len(data.groups)]
    for code in codes:
        cells = [fmt(fire_rate(data.items(mode, size, [g]), cfg, code)) for g in data.groups]
        lines.append(f"| {code} | " + " | ".join(cells) + " |")
    return lines


def no_meter_table(data: Data, cfg: GuidanceConfig) -> List[str]:
    cols = ["readable", "unreadable", "all meters"] + [f"{g} passed as meter" for g in data.non_meter]
    lines = ["| Setting | " + " | ".join(f"{c}" for c in cols) + " |", "|---|" + "---|" * len(cols)]
    settings = [("photo", data.photo_size, f"/submit-photo (YOLO {data.photo_size})")]
    settings += [("frame", s, f"/guide-frame at {s}") for s in data.sizes]
    for mode, size, label in settings:
        meters = ["readable", "unreadable"]
        cells = [fmt(fire_rate(data.items(mode, size, [g]), cfg, "NO_METER")) for g in meters]
        cells.append(fmt(fire_rate(data.items(mode, size, meters), cfg, "NO_METER")))
        for g in data.non_meter:
            r = fire_rate(data.items(mode, size, [g]), cfg, "NO_METER")
            cells.append(fmt(None if r is None else 100 - r))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return lines


def timing_table(data: Data) -> List[str]:
    lines = ["| Call | Median | 90th percentile |", "|---|---|---|"]
    keys = [("photo", data.photo_size, "/submit-photo (incl. quality gate and reader)")]
    keys += [("frame", s, f"/guide-frame, YOLO at {s}") for s in data.sizes]
    for mode, size, label in keys:
        ms = sorted(data.ms[(mode, size)])
        lines.append(f"| {label} | {median(ms):.0f} ms | {ms[int(0.9 * (len(ms) - 1))]:.0f} ms |")
    return lines


def run_report(args) -> None:
    cfg = GuidanceConfig.load(quality_threshold=load_model_config()["quality_gate"]["threshold"])
    data = Data(args.csv)
    out: List[str] = []

    out += ["## Data", "", "| Group | Images |", "|---|---|"]
    out += [f"| {g} | {data.count(g)} |" for g in data.groups]
    out += ["", "## NO_METER", "",
            "Share of real meter photos wrongly flagged NO_METER, and share of non-meter images that "
            "wrongly pass as a meter:", ""]
    out += no_meter_table(data, cfg)

    out += ["", f"## Code rates: /submit-photo (YOLO {data.photo_size}, quality gate and reader on the crop)", ""]
    out += rates_table(data, cfg, "photo", data.photo_size, PHOTO_CODES)
    for size in data.sizes:
        out += ["", f"## Code rates: /guide-frame, YOLO at {size}", ""]
        out += rates_table(data, cfg, "frame", size, FRAME_CODES)
    out += ["", "## Timing (CPU, warm)", ""] + timing_table(data)
    report = "\n".join(out)
    print(report)

    print("\n\n# Threshold suggestions (current config shown in brackets)")
    print(f"\nNO_METER window confidence keeping >= {TARGET_METERS_KEPT:.0f}% of readable+unreadable photos"
          f" [now {cfg.no_meter_window_conf}]:")
    print(f"  /submit-photo: {choose_no_meter(data, cfg, 'photo', data.photo_size)}")
    for size in data.sizes:
        print(f"  /guide-frame at {size}: {choose_no_meter(data, cfg, 'frame', size)}")
    print("  sweep (window conf: % meters flagged / % of each non-meter set passing as a meter):")
    for mode, size in [("photo", data.photo_size)] + [("frame", s) for s in data.sizes]:
        cells = []
        for c in NO_METER_CANDIDATES[::2]:
            v = dataclasses.replace(cfg, no_meter_window_conf=c)
            flagged = fire_rate(data.items(mode, size, ["readable", "unreadable"]), v, "NO_METER")
            passing = [100 - fire_rate(data.items(mode, size, [g]), v, "NO_METER") for g in data.non_meter]
            cells.append(f"{c}: {flagged:.1f}/" + "/".join(f"{p:.1f}" for p in passing))
        print(f"    {mode} {size}: " + "   ".join(cells))
    for code in SWEEPS:
        attr, table, best = choose_check(data, cfg, code)
        print(f"\n{code} ({attr}) [now {getattr(cfg, attr)}]   value: readable / unreadable")
        print("  " + "   ".join(f"{v}: {r:.0f}/{u:.0f}" for v, r, u in table))
        print(f"  -> {best[0]} (readable {best[1]:.1f}%, unreadable {best[2]:.1f}%)" if best else
              f"  -> no value fires on <= {MAX_READABLE_NAG:.0f}% of readable and >= {MIN_GAP:.0f} points"
              " more on unreadable: turn it off or soften its message")

    readable = data.items("photo", data.photo_size, ["readable"])
    unreadable = data.items("photo", data.photo_size, ["unreadable"])
    r, u = fire_rate(readable, cfg, "HARD_TO_READ"), fire_rate(unreadable, cfg, "HARD_TO_READ")
    if r is not None and u is not None and r > u:
        print(f"\nSTOP: HARD_TO_READ fires more on readable ({r:.1f}%) than unreadable ({u:.1f}%) photos."
              " The quality gate's positive_class_index in model_config.json is probably wrong.")

    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(args.header.read_text() + "\n" + report + "\n" if args.header else report + "\n")
        print(f"\nWrote {args.markdown}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    m = sub.add_parser("measure")
    m.add_argument("--photos", type=Path, required=True)
    m.add_argument("--readable-csv", type=Path, required=True)
    m.add_argument("--unreadable-csv", type=Path, required=True)
    m.add_argument("--non-meter", action="append", default=[], help="NAME=FOLDER, repeatable")
    m.add_argument("--sizes", type=int, nargs="+", default=[640, 416, 320])
    m.add_argument("--csv", type=Path, required=True)
    m.add_argument("--limit", type=int, help="Only the first N images (for a quick test)")
    r = sub.add_parser("report")
    r.add_argument("--csv", type=Path, required=True)
    r.add_argument("--markdown", type=Path, help="Write the tables (no file names) to this file")
    r.add_argument("--header", type=Path, help="Markdown to put above the tables")
    args = parser.parse_args()
    run_measure(args) if args.command == "measure" else run_report(args)


if __name__ == "__main__":
    main()
