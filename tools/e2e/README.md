# Live end-to-end check

Runs the whole flow on the live site in a headless browser, as a household and an officer do:
sign in with a code, read the meter (a real photo), held for checking, officer accepts, bill,
pay, confirmation. It changes data: use a fresh DEMO- household each time.

```bash
cd tools/e2e && npm install
node live_e2e.mjs https://wasac-smart-billing-qt9t.vercel.app <meter photo.jpg> <staff password> "0700 000 017"
```

It needs a Chromium build (`npx playwright-core install chromium-headless-shell`, or pass its path
as the 5th argument). Screenshots of every step are written to `out/`.
