# App icons (source)

The Mubazi mark: an imigongo zigzag drawing an "M" (the geometric relief art of eastern Rwanda is
built from zigzags and diamonds), white on Kivu deep blue, with a terracotta diamond and a faint
diamond pattern. The same drawing as `src/components/Logo/Logo.tsx`. No water drops or waves.

| Source | Rendered to | Used for |
|---|---|---|
| `icon.svg` | `icon-192.png`, `icon-512.png` | Android home screen, install dialog |
| `icon-maskable.svg` | `icon-maskable-512.png` | Android adaptive icons (content inside the 80% safe zone) |
| `icon-full.svg` | `apple-touch-icon.png` (180) | iPhone home screen (iOS rounds the corners) |
| `favicon.svg` | `favicon.svg`, `favicon-32.png` | Browser tab (the mark alone, readable when tiny) |

After changing an SVG, render the PNGs again: `node tools/e2e/render_icons.mjs <chrome path>` from
the repository root (headless Chromium), which also copies `favicon.svg` to `public/`.
