# Submission checklist

**Attempt 1:** the GitHub link. README must show working video and report links, opened in a private browser window.

**Attempt 2:** a ZIP of the same repository, plus the report PDF and the video file. No APK: Mubazi is an installable web
app (PWA), so there is nothing to build for a phone store.

Make the ZIP from git, so ignored secrets cannot enter it:

    git archive --format=zip --prefix=mubazi/ -o mubazi-submission.zip origin/main

Then add the PDF and the video, and confirm none of these are inside: `.env`, `STAFF_LOGIN.local.txt`,
`backend/calibration/`, `*.pt`, `*.onnx`. Model files are downloaded separately because of their licence; the README explains this.
