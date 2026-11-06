"""Archive the committed repository and submission artifacts without local secrets or dependencies.

Attempt 2: python tools/package_submission.py --video /path/to/video.mp4 --out /path/to/submission.zip
Source only: python tools/package_submission.py --source-only --out /path/to/source.zip
Requires the optional docs/report/requirements.txt dependencies to verify the PDF page limit.
"""
import argparse
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import zipfile

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "wasac-smart-billing/"
REPORT = "docs/report/Mubazi_Technical_Report.pdf"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def video_path(raw):
    path = Path(raw).expanduser().resolve()
    if not path.is_file() or path.stat().st_size < 1024:
        raise ValueError("Supply the actual recording file, not a link, empty file or shortcut.")
    with path.open("rb") as stream:
        header = stream.read(32)
    if not (b"ftyp" in header or header.startswith(b"\x1a\x45\xdf\xa3") or header.startswith(b"RIFF")):
        raise ValueError("The recording is not a recognized MP4/MOV, WebM/MKV or AVI media container.")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--video", help="Actual walkthrough recording; required for a complete Attempt 2")
    mode.add_argument("--source-only", action="store_true", help="Repository archive; NOT a complete Attempt 2")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if git("status", "--porcelain").strip():
        parser.error("Commit the intended source/report changes first so both attempts use the same revision.")
    try:
        video = video_path(args.video) if args.video else None
    except ValueError as error:
        parser.error(str(error))
    output = args.out.expanduser().resolve()
    if output.exists():
        parser.error("Output already exists; choose a new filename to preserve the earlier package.")
    output.parent.mkdir(parents=True, exist_ok=True)
    commit = git("rev-parse", "HEAD").decode().strip()
    tracked = set(git("ls-files", "-z").decode().split("\0")) - {""}
    pages = len(PdfReader(io.BytesIO(git("show", f"HEAD:{REPORT}"))).pages)
    if pages > 5:
        parser.error(f"The committed report has {pages} pages; the maximum is five.")
    for name in tracked:
        if (Path(name).name == ".env" or (".env." in Path(name).name and not name.endswith(".env.example"))
                or Path(name).suffix in (".pt", ".pth", ".onnx", ".pkl", ".joblib", ".h5", ".dump", ".db", ".sqlite3")
                or name.endswith(".local.txt")):
            parser.error(f"Unexpected private/runtime file is tracked: {name}. Review it before packaging.")

    manifest = {"commit": commit, "mode": "attempt-2" if video else "source-only-missing-video",
                "report_pages": pages, "video_included": bool(video), "files": {}}

    def write_bytes(archive, name, content, compression=zipfile.ZIP_DEFLATED, file_mode=0o644, modified=None):
        timestamp = datetime.fromtimestamp(modified) if modified else datetime.now()
        info = zipfile.ZipInfo(PREFIX+name, date_time=timestamp.timetuple()[:6])
        info.create_system, info.external_attr, info.compress_type = 3, (0o100000 | file_mode) << 16, compression
        archive.writestr(info, content)
        manifest["files"][name] = hashlib.sha256(content).hexdigest()

    try:
        with tempfile.TemporaryFile() as snapshot, zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
            subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=ROOT, stdout=snapshot, check=True)
            snapshot.seek(0)
            with tarfile.open(fileobj=snapshot, mode="r:") as source:
                for member in source:
                    if member.isfile():
                        write_bytes(archive, member.name, source.extractfile(member).read(),
                                    file_mode=member.mode, modified=member.mtime)
                    elif member.issym():
                        info = zipfile.ZipInfo(PREFIX+member.name)
                        info.create_system, info.external_attr = 3, 0o120777 << 16
                        archive.writestr(info, member.linkname)
                        manifest["files"][member.name] = hashlib.sha256(member.linkname.encode()).hexdigest()
            assert tracked <= set(manifest["files"]), "A tracked file is missing from the archive"
            write_bytes(archive, "submission/Mubazi_Technical_Report.pdf", git("show", f"HEAD:{REPORT}"))
            write_bytes(archive, "submission/COMMIT.txt", (commit+"\n").encode()+git("log", "-20", "--format=%h %s"))
            web_build = ROOT/"frontend/build"
            manifest["production_web_build_included"] = (web_build/"index.html").is_file()
            if manifest["production_web_build_included"]:
                for path in sorted(web_build.rglob("*")):
                    if path.is_file():
                        write_bytes(archive, path.relative_to(ROOT).as_posix(), path.read_bytes())
            if video:
                name = "submission/Mubazi_Walkthrough"+video.suffix.lower()
                digest = hashlib.sha256()
                info = zipfile.ZipInfo(PREFIX+name)
                info.compress_type = zipfile.ZIP_STORED
                with video.open("rb") as src, archive.open(info, "w", force_zip64=True) as dst:
                    while block := src.read(1024*1024):
                        digest.update(block)
                        dst.write(block)
                manifest["files"][name] = digest.hexdigest()
            status = ("The actual walkthrough recording is included." if video else
                      "SOURCE ONLY: the actual walkthrough recording is missing. This is NOT a complete Attempt 2.")
            instructions = f"""Mubazi submission — source commit {commit}

{status}
The technical report is in submission/Mubazi_Technical_Report.pdf ({pages} pages).
Source files are byte-for-byte from the same committed GitHub revision.
README.md contains installation, runtime requirements, live app and walkthrough links.

This is a browser/PWA application: a native executable/APK is not applicable.
When included, frontend/build is the production web build, not a standalone offline executable.
Start the backend using the README, then from frontend run npm ci and npm run preview.

Model weights, raw private meter photos, passwords, .env files, node_modules and virtual environments
are intentionally excluded. Without private weights the application offers manual digit entry.
GitHub retains the full meaningful commit history; COMMIT.txt identifies this snapshot and recent commits.
"""
            write_bytes(archive, "submission/READ_FIRST.txt", instructions.encode())
            archive.writestr(PREFIX+"submission/MANIFEST.json", json.dumps(manifest, indent=2)+"\n")
        with zipfile.ZipFile(output) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("ZIP integrity check failed")
        print(f"Wrote {output}: {len(tracked)} tracked source files; report {pages} pages; video included: {bool(video)}")
    except Exception:
        # Preserve an incomplete archive for diagnosis, but never leave it looking submission-ready.
        if output.exists():
            output.rename(output.with_name(output.name+".incomplete"))
        raise


if __name__ == "__main__":
    main()
