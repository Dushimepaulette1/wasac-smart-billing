"""Download the three model weight files (not kept in git) and verify their checksums.

    MODEL_BASE_URL=https://github.com/<owner>/<repo>/releases/download/<tag> python scripts/download_models.py

Each file is fetched from <MODEL_BASE_URL>/<file name> into ML_WEIGHTS_DIR (default backend/ml).
Files already present with the right checksum are skipped; use --force to fetch them again.
Checksums come from backend/ml/weights.sha256.json.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vision.config import ML_CODE_DIR, weights_dir  # noqa: E402

CHUNK = 1 << 20


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def download(url: str, dest: Path, expected_sha: str) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as resp, open(tmp, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while block := resp.read(CHUNK):
            out.write(block)
            done += len(block)
            if total:
                print(f"\r  {dest.name}: {done * 100 // total}% of {total / 1e6:.1f} MB", end="", flush=True)
    print()
    actual = sha256(tmp)
    if actual != expected_sha:
        tmp.unlink()
        raise SystemExit(f"Checksum mismatch for {dest.name}: expected {expected_sha}, got {actual}. Nothing saved.")
    tmp.replace(dest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=os.getenv("MODEL_BASE_URL"), help="Defaults to $MODEL_BASE_URL")
    parser.add_argument("--dest", type=Path, default=None, help="Defaults to $ML_WEIGHTS_DIR or backend/ml")
    parser.add_argument("--force", action="store_true", help="Download even if a valid file exists")
    args = parser.parse_args()
    if not args.base_url:
        sys.exit("Set MODEL_BASE_URL (or pass --base-url) to the folder or release that holds the .pt files.")

    dest_dir = args.dest or weights_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    expected = json.loads((ML_CODE_DIR / "weights.sha256.json").read_text())
    base = args.base_url.rstrip("/")

    for name, info in expected.items():
        dest = dest_dir / name
        if dest.exists() and not args.force and sha256(dest) == info["sha256"]:
            print(f"  {name}: already present and verified")
            continue
        print(f"  {name}: downloading from {base}/{name}")
        download(f"{base}/{name}", dest, info["sha256"])
        print(f"  {name}: verified")
    print(f"All model files are in {dest_dir}")


if __name__ == "__main__":
    main()
