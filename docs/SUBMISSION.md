# Submission contents and reproducibility

## Attempt 1 — GitHub repository

Submit the [repository](https://github.com/Dushimepaulette1/wasac-smart-billing). Its README provides:

- Overview, workflow, scope and simulation boundaries.
- Installation, Python/Node/database requirements, frameworks, and repository structure.
- The [walkthrough video](https://youtu.be/5i7eupcCpGQ).
- The [technical report PDF](report/Mubazi_Technical_Report.pdf), at most five pages, covering scope,
  functionality, testing/results, code quality and limitations.

Source, tests, training notebook, dependency manifests, deployment files and evidence are versioned.
GitHub contains the meaningful commit history. Public unauthenticated access to the existing report
and YouTube metadata was checked on 6 November 2026; metadata access does not replace watching the
complete video. Check the Actions results for the exact submitted commit.

## Attempt 2 — same repository revision plus artifacts

The stated instructions require the ZIP to contain the **actual video file**. A YouTube URL or a
text shortcut is sufficient for Attempt 1's link requirement, but is not the video file required by
Attempt 2. Use the original recording or a downloaded copy of your own upload. A 720p MP4 copy with audio was
retrieved from the author's YouTube upload on 6 November 2026 for the prepared Attempt 2 archive.

From a clean, committed checkout, with the optional report dependencies installed:

```sh
python -m pip install -r docs/report/requirements.txt
python tools/package_submission.py --video /path/to/walkthrough.mp4 --out /path/to/Mubazi_Attempt2.zip
```

The archive contains every tracked file from that commit under `wasac-smart-billing/`, a convenient
PDF copy, the actual recording, a commit identifier/recent history, and checksums. If `frontend/build`
exists it includes that production web build too. The tool checks the report page limit, refuses
dirty checkouts and private/runtime files, and verifies ZIP integrity.

For a repository-source archive while the recording is unavailable:

```sh
python tools/package_submission.py --source-only --out /path/to/Mubazi_Repository_Source.zip
```

This is explicitly labelled **not a complete Attempt 2**. The previous document/presentation handoff
pack is also not the full repository ZIP required here.

## Executable / APK applicability

Mubazi is a web application/PWA, not a native Android or desktop application. A native executable or
APK is therefore not applicable. Use the live URL or run the supplied backend and frontend locally.
The compiled web assets can be served with `npm run preview` from `frontend/` after installing its
dependencies; the backend must also run. Opening index.html directly is not the supported setup.

Private model weights and household images are not redistributed. Dependency folders, databases,
backups, secrets and virtual environments are excluded; install dependencies from the manifests.
Without model files, the working application falls back to manual reading entry. This boundary is
documented in the README and report so the archive does not imply standalone recognition capability.
