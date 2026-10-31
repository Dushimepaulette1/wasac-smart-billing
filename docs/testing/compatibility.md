# Compatibility and page speed

Made by `tools/e2e/compat_check.mjs` on 2026-10-31 against a local build. Browser engines
and device sizes are real engines at simulated sizes, and the slow networks and CPU are simulated, not real phones.
Real-phone results are in `real_phone_results.md`.

## Browsers and screen sizes

| Browser | Size | Page | Result | Load (ms) |
|---|---|---|---|---|
| chromium 141.0.7390.37 | small phone (360x640) | / | pass | 1363 |
| chromium 141.0.7390.37 | small phone (360x640) | /sign-in | pass | 688 |
| chromium 141.0.7390.37 | small phone (360x640) | /staff/sign-in | pass | 988 |
| chromium 141.0.7390.37 | phone (390x844) | / | pass | 1138 |
| chromium 141.0.7390.37 | phone (390x844) | /sign-in | pass | 981 |
| chromium 141.0.7390.37 | phone (390x844) | /staff/sign-in | pass | 1244 |
| chromium 141.0.7390.37 | tablet (768x1024) | / | pass | 1087 |
| chromium 141.0.7390.37 | tablet (768x1024) | /sign-in | pass | 831 |
| chromium 141.0.7390.37 | tablet (768x1024) | /staff/sign-in | pass | 1067 |
| chromium 141.0.7390.37 | laptop (1366x768) | / | pass | 1150 |
| chromium 141.0.7390.37 | laptop (1366x768) | /sign-in | pass | 918 |
| chromium 141.0.7390.37 | laptop (1366x768) | /staff/sign-in | pass | 817 |
| firefox | all | all | not run: Error: browserType.launch:  |
| webkit | all | all | not run: Error: browserType.launch:  |

## Landing page speed, phone size, no cache

| Conditions | First paint (ms) | Page loaded (ms) | Downloaded (KB) |
|---|---|---|---|
| no limit | 1132 | 815 | 5426 |
| slow 3G, 4x slower CPU | 111108 | 110163 | 5376 |
| fast 3G, 4x slower CPU | 30504 | 28512 | 5426 |
