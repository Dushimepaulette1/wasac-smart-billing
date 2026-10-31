# End-to-end check

Runs the whole flow in a headless browser, as a household and an officer do:
sign in with a code, read the meter (a real photo), held for checking, officer accepts, bill,
pay, confirmation. It changes data: use a fresh DEMO- household each time.

```bash
cd tools/e2e && npm install
E2E_ALLOW_LIVE=1 node live_e2e.mjs https://wasac-smart-billing-qt9t.vercel.app <meter photo.jpg> <staff password> "0700 000 017"
```

It refuses anything but localhost unless `E2E_ALLOW_LIVE=1` is set, because it changes data.
Environment: `E2E_STAFF_USER` (staff username), `E2E_READING` (8 digits to type on the confirm page,
needed when the models are not available), `E2E_REJECT_PHONE` (a second demo household, for the
reject path), `E2E_NO_MODELS=1` (the models are not installed, so no photo is kept).

It needs a Chromium build (`npx playwright-core install chromium-headless-shell`, or pass its path
as the 5th argument). Screenshots of every step are written to `out/`.
