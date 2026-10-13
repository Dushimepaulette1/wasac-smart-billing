"""Download about 50 everyday images from the COCO 2017 validation set (non-meter calibration set).

    python scripts/download_coco_samples.py --out calibration/not_meters_coco

Images are fetched one by one from images.cocodataset.org by their val2017 ids. They are for local
calibration only and must not be committed (COCO images carry their Flickr authors' licences).
"""
import argparse
import urllib.error
import urllib.request
from pathlib import Path

# The first val2017 image ids; a few may 404, so more are listed than needed.
VAL2017_IDS = [
    139, 285, 632, 724, 776, 785, 802, 872, 885, 1000, 1268, 1296, 1353, 1425, 1490, 1503, 1532,
    1584, 1675, 1761, 1818, 1993, 2006, 2149, 2153, 2157, 2261, 2299, 2431, 2473, 2532, 2587, 2592,
    2685, 2923, 3156, 3255, 3501, 3553, 3661, 3845, 3934, 4134, 4395, 4495, 4765, 4795, 5001, 5037,
    5060, 5193, 5477, 5503, 5529, 5586, 5600, 5992, 6012, 6040, 6213, 6460, 6471, 6614, 6723, 6763,
    6771, 6818, 6894, 6954, 7088, 7108, 7278, 7281, 7386, 7511, 7574, 7784, 7816, 7818, 7888,
]
URL = "http://images.cocodataset.org/val2017/{:012d}.jpg"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    got = failed = 0
    for image_id in VAL2017_IDS:
        if got >= args.count:
            break
        dest = args.out / f"{image_id:012d}.jpg"
        if dest.exists():
            got += 1
            continue
        try:
            with urllib.request.urlopen(URL.format(image_id), timeout=20) as resp:
                dest.write_bytes(resp.read())
            got += 1
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            failed += 1
            print(f"  {image_id}: {e}")
            if failed >= 5 and got == 0:
                raise SystemExit("COCO download looks blocked; skipping the COCO set.")
    print(f"{got} COCO images in {args.out} ({failed} failed)")


if __name__ == "__main__":
    main()
