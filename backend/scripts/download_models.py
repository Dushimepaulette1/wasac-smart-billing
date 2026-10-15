"""Download the three model weight files (not kept in git) and verify their SHA-256 checksums.

Two ways to say where the files are:

  One link per file (e.g. Google Drive; each Drive file has its own id):
    MODEL_URLS="best.pt=<link>,meter_reader.pt=<link>,quality_gate.pt=<link>" python scripts/download_models.py

  One folder for all three (e.g. a release, or any server with <base>/<file name>):
    MODEL_BASE_URL=https://example.org/models python scripts/download_models.py

Google Drive share links (https://drive.google.com/file/d/<id>/view?...) are turned into direct
downloads. The Drive files must be shared as "Anyone with the link"; keep the links in .env, not git.
Files already present with the right checksum are skipped (--force fetches them again). Nothing is
saved unless its checksum matches backend/ml/weights.sha256.json.

MODEL_FORMAT (or --format) picks the files: "pt" (default, PyTorch) or "onnx" (the small deployment,
made by scripts/export_onnx.py: best.onnx, meter_reader.onnx, quality_gate.onnx).
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv  # noqa: E402

from vision.config import ML_CODE_DIR, weights_dir  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")  # the Drive links live in backend/.env

CHUNK = 1 << 20
_DRIVE_ID = re.compile(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:[^#]*&)?id=)([\w-]+)")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def direct_url(url: str) -> str:
    """Google Drive share/view links -> the direct-download endpoint; other URLs unchanged."""
    match = _DRIVE_ID.search(url)
    if match:
        return f"https://drive.usercontent.google.com/download?id={match.group(1)}&export=download&confirm=t"
    return url


def parse_urls(spec: Optional[str]) -> Dict[str, str]:
    urls = {}
    for part in filter(None, (p.strip() for p in (spec or "").split(","))):
        name, sep, url = part.partition("=")
        if not sep:
            # Never echo the entry: it may contain a private link.
            raise SystemExit("A MODEL_URLS entry is not in the form name=url")
        if url.strip():  # "best.pt=" (as in .env.example) means not set yet
            urls[name.strip()] = url.strip()
    return urls


class DownloadError(Exception):
    """A failure whose message is safe to log: it never contains a URL or a secret."""


def download(url: str, dest: Path, expected_sha: str) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "wasac-download-models"})
    with urllib.request.urlopen(request, timeout=60) as resp:
        if "text/html" in (resp.headers.get("Content-Type") or ""):
            raise DownloadError(
                "the link returned a web page, not the file. For Google Drive, share the "
                "file as 'Anyone with the link' and use its share link or file id"
            )
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(tmp, "wb") as out:
            while block := resp.read(CHUNK):
                out.write(block)
                done += len(block)
                if total:
                    print(f"\r  {dest.name}: {done * 100 // total}% of {total / 1e6:.1f} MB", end="", flush=True)
    print()
    actual = sha256(tmp)
    if actual != expected_sha:
        tmp.unlink()
        raise DownloadError(f"checksum mismatch (expected {expected_sha}, got {actual}); nothing saved")
    tmp.replace(dest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=os.getenv("MODEL_BASE_URL"), help="Defaults to $MODEL_BASE_URL")
    parser.add_argument("--urls", default=os.getenv("MODEL_URLS"), help="name=url,... Defaults to $MODEL_URLS")
    parser.add_argument("--dest", type=Path, default=None, help="Defaults to $ML_WEIGHTS_DIR or backend/ml")
    parser.add_argument("--force", action="store_true", help="Download even if a valid file exists")
    parser.add_argument("--format", choices=("pt", "onnx"), default=os.getenv("MODEL_FORMAT", "pt"),
                        help="Which files: pt (default) or onnx. Defaults to $MODEL_FORMAT")
    args = parser.parse_args()

    every = json.loads((ML_CODE_DIR / "weights.sha256.json").read_text())
    expected = {name: info for name, info in every.items() if name.endswith(f".{args.format}")}
    per_file = parse_urls(args.urls)
    unknown = set(per_file) - set(every)
    if unknown:
        # Do not echo the unknown names: a stray link (links contain '=') would be printed here.
        sys.exit(f"MODEL_URLS has {len(unknown)} entry/entries with an unknown file name. "
                 f"Use exactly: {', '.join(expected)}")

    dest_dir = args.dest or weights_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    failed = []
    for name, info in expected.items():
        dest = dest_dir / name
        if dest.exists() and not args.force and sha256(dest) == info["sha256"]:
            print(f"  {name}: already present and verified")
            continue
        if name in per_file:
            url = direct_url(per_file[name])
        elif args.base_url:
            url = f"{args.base_url.rstrip('/')}/{name}"
        else:
            print(f"  {name}: failed (no link set in MODEL_URLS or MODEL_BASE_URL)")
            failed.append(name)
            continue
        print(f"  {name}: downloading")
        try:
            download(url, dest, info["sha256"])
        except DownloadError as e:
            print(f"\n  {name}: failed ({e})")
            failed.append(name)
        except Exception as e:  # noqa: BLE001 - its message may contain the URL; log only the type
            print(f"\n  {name}: failed ({type(e).__name__})")
            failed.append(name)
        else:
            print(f"  {name}: verified")
    if failed:
        # Non-zero exit; the API still starts, and /health lists the missing models.
        sys.exit(f"Download failed for: {', '.join(failed)}")
    print(f"All model files are in {dest_dir}")


if __name__ == "__main__":
    main()
