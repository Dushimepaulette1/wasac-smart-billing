# Compatibility and page speed

Made by `tools/e2e/compat_check.mjs` on 2026-11-06 against a local build. Browser engines
and device sizes are real engines at simulated sizes, and the slow networks and CPU are simulated, not real phones.

## Browsers and screen sizes

| Browser | Size | Page | Result | Load (ms) |
|---|---|---|---|---|
| chromium 141.0.7390.37 | small phone (360x640) | / | pass | 84 |
| chromium 141.0.7390.37 | small phone (360x640) | /sign-in | pass | 52 |
| chromium 141.0.7390.37 | small phone (360x640) | /staff/sign-in | pass | 44 |
| chromium 141.0.7390.37 | phone (390x844) | / | pass | 58 |
| chromium 141.0.7390.37 | phone (390x844) | /sign-in | pass | 44 |
| chromium 141.0.7390.37 | phone (390x844) | /staff/sign-in | pass | 42 |
| chromium 141.0.7390.37 | tablet (768x1024) | / | pass | 61 |
| chromium 141.0.7390.37 | tablet (768x1024) | /sign-in | pass | 44 |
| chromium 141.0.7390.37 | tablet (768x1024) | /staff/sign-in | pass | 42 |
| chromium 141.0.7390.37 | laptop (1366x768) | / | pass | 56 |
| chromium 141.0.7390.37 | laptop (1366x768) | /sign-in | pass | 42 |
| chromium 141.0.7390.37 | laptop (1366x768) | /staff/sign-in | pass | 41 |
| firefox 142.0.1 | small phone (360x640) | / | pass | 165 |
| firefox 142.0.1 | small phone (360x640) | /sign-in | pass | 75 |
| firefox 142.0.1 | small phone (360x640) | /staff/sign-in | pass | 68 |
| firefox 142.0.1 | phone (390x844) | / | pass | 80 |
| firefox 142.0.1 | phone (390x844) | /sign-in | pass | 55 |
| firefox 142.0.1 | phone (390x844) | /staff/sign-in | pass | 62 |
| firefox 142.0.1 | tablet (768x1024) | / | pass | 81 |
| firefox 142.0.1 | tablet (768x1024) | /sign-in | pass | 55 |
| firefox 142.0.1 | tablet (768x1024) | /staff/sign-in | pass | 61 |
| firefox 142.0.1 | laptop (1366x768) | / | pass | 84 |
| firefox 142.0.1 | laptop (1366x768) | /sign-in | pass | 102 |
| firefox 142.0.1 | laptop (1366x768) | /staff/sign-in | pass | 91 |
| webkit 26.0 | small phone (360x640) | / | pass | 143 |
| webkit 26.0 | small phone (360x640) | /sign-in | pass | 106 |
| webkit 26.0 | small phone (360x640) | /staff/sign-in | pass | 88 |
| webkit 26.0 | phone (390x844) | / | pass | 142 |
| webkit 26.0 | phone (390x844) | /sign-in | pass | 104 |
| webkit 26.0 | phone (390x844) | /staff/sign-in | pass | 94 |
| webkit 26.0 | tablet (768x1024) | / | pass | 136 |
| webkit 26.0 | tablet (768x1024) | /sign-in | pass | 106 |
| webkit 26.0 | tablet (768x1024) | /staff/sign-in | pass | 107 |
| webkit 26.0 | laptop (1366x768) | / | pass | 169 |
| webkit 26.0 | laptop (1366x768) | /sign-in | pass | 98 |
| webkit 26.0 | laptop (1366x768) | /staff/sign-in | pass | 106 |

## Landing page speed, phone size, no cache

| Conditions | First paint (ms) | Page loaded (ms) | Downloaded (KB) |
|---|---|---|---|
| no limit | 60 | 18 | 198 |
| slow 3G, 4x slower CPU | 3388 | 3267 | 122 |
| fast 3G, 4x slower CPU | 1068 | 947 | 122 |
