# App icons (source)

The Mubazi mark: a deep navy (#0B2244) tile with a geometric white "M" at one even stroke weight
and a sky-blue point under its centre. The same drawing as `src/components/Logo/Logo.tsx`.

| Source | Rendered to | Used for |
|---|---|---|
| `icon.svg` | `icon-192.png`, `icon-512.png` | Android home screen, install dialog |
| `icon-maskable.svg` | `icon-maskable-512.png` | Android adaptive icons (content inside the 80% safe zone) |
| `icon-full.svg` | `apple-touch-icon.png` (180) | iPhone home screen (iOS rounds the corners) |
| `favicon.svg` | `favicon.svg`, `favicon-32.png` | Browser tab |

After changing an SVG, render the PNGs again from the repository root:
`node tools/e2e/render_icons.mjs <path to chrome or chrome-headless-shell>` (it also copies
`favicon.svg` to `public/`).
