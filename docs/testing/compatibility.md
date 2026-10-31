# Compatibility and page speed

Made by `tools/e2e/compat_check.mjs` in GitHub Actions run 41210499849 (the `compatibility` job, Ubuntu), on the production
build, on 31 October 2026. These are real browser engines at simulated screen sizes. The slow networks and slower CPU are
simulated, not real phones. WebKit stands in for Safari but is not Safari on an iPhone. Real-phone results are in
`real_phone_results.md`.

**Result: 36 of 36 passed.** Each page loaded, showed its heading, had no sideways scroll and no page errors.

| Browser | Size | Page | Result | Load (ms) |
|---|---|---|---|---|
| chromium 141.0.7390.37 | small phone (360x640) | / | pass | 188 |
| chromium 141.0.7390.37 | small phone (360x640) | /sign-in | pass | 109 |
| chromium 141.0.7390.37 | small phone (360x640) | /staff/sign-in | pass | 100 |
| chromium 141.0.7390.37 | phone (390x844) | / | pass | 145 |
| chromium 141.0.7390.37 | phone (390x844) | /sign-in | pass | 104 |
| chromium 141.0.7390.37 | phone (390x844) | /staff/sign-in | pass | 100 |
| chromium 141.0.7390.37 | tablet (768x1024) | / | pass | 137 |
| chromium 141.0.7390.37 | tablet (768x1024) | /sign-in | pass | 102 |
| chromium 141.0.7390.37 | tablet (768x1024) | /staff/sign-in | pass | 99 |
| chromium 141.0.7390.37 | laptop (1366x768) | / | pass | 130 |
| chromium 141.0.7390.37 | laptop (1366x768) | /sign-in | pass | 100 |
| chromium 141.0.7390.37 | laptop (1366x768) | /staff/sign-in | pass | 96 |
| firefox 142.0.1 | small phone (360x640) | / | pass | 425 |
| firefox 142.0.1 | small phone (360x640) | /sign-in | pass | 175 |
| firefox 142.0.1 | small phone (360x640) | /staff/sign-in | pass | 212 |
| firefox 142.0.1 | phone (390x844) | / | pass | 176 |
| firefox 142.0.1 | phone (390x844) | /sign-in | pass | 146 |
| firefox 142.0.1 | phone (390x844) | /staff/sign-in | pass | 146 |
| firefox 142.0.1 | tablet (768x1024) | / | pass | 206 |
| firefox 142.0.1 | tablet (768x1024) | /sign-in | pass | 149 |
| firefox 142.0.1 | tablet (768x1024) | /staff/sign-in | pass | 177 |
| firefox 142.0.1 | laptop (1366x768) | / | pass | 212 |
| firefox 142.0.1 | laptop (1366x768) | /sign-in | pass | 151 |
| firefox 142.0.1 | laptop (1366x768) | /staff/sign-in | pass | 167 |
| webkit 26.0 | small phone (360x640) | / | pass | 465 |
| webkit 26.0 | small phone (360x640) | /sign-in | pass | 248 |
| webkit 26.0 | small phone (360x640) | /staff/sign-in | pass | 255 |
| webkit 26.0 | phone (390x844) | / | pass | 414 |
| webkit 26.0 | phone (390x844) | /sign-in | pass | 261 |
| webkit 26.0 | phone (390x844) | /staff/sign-in | pass | 252 |
| webkit 26.0 | tablet (768x1024) | / | pass | 432 |
| webkit 26.0 | tablet (768x1024) | /sign-in | pass | 268 |
| webkit 26.0 | tablet (768x1024) | /staff/sign-in | pass | 381 |
| webkit 26.0 | laptop (1366x768) | / | pass | 646 |
| webkit 26.0 | laptop (1366x768) | /sign-in | pass | 276 |
| webkit 26.0 | laptop (1366x768) | /staff/sign-in | pass | 233 |

## Landing page speed, phone size, no cache

| Conditions | First paint (ms) | Page loaded (ms) | Downloaded (KB) |
|---|---|---|---|
| no limit | 168 | 44 | 194 |
| slow 3G, 4x slower CPU | 3516 | 3246 | 123 |
| fast 3G, 4x slower CPU | 1228 | 945 | 194 |
