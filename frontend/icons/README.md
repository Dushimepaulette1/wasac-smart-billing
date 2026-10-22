# App icons (source)

The PWA icons are drawn here as SVG and rendered to PNG into `frontend/public/`:
a meter counter (black cubic-metre cells, one red litre cell, white digits in the app's
counter font) on the night-blue stage, the app's signature element. No water drops or waves.

| Source | Rendered to | Used for |
|---|---|---|
| `icon.svg` | `icon-192.png`, `icon-512.png` | Android home screen, install dialog |
| `icon-maskable.svg` | `icon-maskable-512.png` | Android adaptive icons (content inside the 80% safe zone) |
| `icon-full.svg` | `apple-touch-icon.png` (180) | iPhone home screen (iOS rounds the corners) |
| `favicon.svg` | `favicon.svg`, `favicon-32.png` | Browser tab (three large cells, readable when tiny) |

After changing an SVG, render the PNGs again at those sizes (any SVG renderer; they were made
with headless Chromium) and copy `favicon.svg` to `public/`.
