# Design plan: Mubazi (v3, "imigongo modern")

Status: built 23/10/2026. Replaces v2 ("deep water at night", kept as `DESIGN_PLAN_v2.md`).
The client asked for a new name and a livelier, more professional look that households are
excited to open and staff enjoy using, with full dark mode, a real spinner, no emojis, and a
refined blue (not the default UI blue).

## 1. Name and mark

**Mubazi**: the everyday Kinyarwanda word for the water meter, understood by every household.
The mark is an **imigongo zigzag drawing an "M"** (imigongo is the geometric relief art of eastern
Rwanda, built from zigzags and nested diamonds), white on Kivu deep blue, with a terracotta
diamond. Source: `src/components/Logo/Logo.tsx`; app icons: `frontend/icons/` (rendered with
`tools/e2e/render_icons.mjs`). WASAC stays the utility: "For WASAC customers", SMS from WASAC.

## 2. Colour (all in `src/styles/tokens.css`, both themes)

| Role | Light | Dark | Check |
|---|---|---|---|
| Page `--bg` | #F6F1E9 warm cream | #0E1015 deep ink | |
| Surface `--surface` | #FFFFFF | #181B23 | |
| Text `--text` | #17181C | #F2EEE7 | 17.7:1 / 14.9:1 on surface |
| Secondary `--text-2` | #575B66 | #AEB2BD | 6.8:1 / 8.1:1 |
| Hint `--text-3` | #6B6F79 | #8A8F9B | 5.0:1 / 5.3:1 (on surface only) |
| Brand `--brand` (Kivu deep) | #1E5470 | #7DBBD3 | white on it 8.2:1; dark text on dark brand 8.4:1 |
| Terracotta `--clay` | #B9472A | #EE8A63 | patterns, accents; never errors |
| Ochre `--ochre` | #D9982B | #F1B652 | decorative only |
| OK / held / danger | #126B41 / #8A5A00 / #B3261E | #5DD39A / #F3C567 / #FF8A80 | each >= 5:1 on its soft fill |
| Chart `--chart-1` | #24739F | #3F93BF | dataviz validator: lightness band, chroma, >= 3:1 |

Contrast was computed, not eyeballed (WCAG formula; the chart colour with the dataviz skill's
`validate_palette.js`). Meter black and meter red stay on the counter only.

**Why dark mode was broken before:** panels were forced light in every theme (the v2 rule
"content lives on light panels"), and several forms hard-coded `#FFFFFF`. Now every surface,
field, select and table reads the theme roles; `base.css` styles bare fields with `:where()` so
components still win.

## 3. Type

- **Bricolage Grotesque** (variable 200-800): headlines, the wordmark, money. Characterful but
  clean; strong at large sizes.
- **Plus Jakarta Sans** (variable 200-800): everything else. Friendly, very legible on cheap
  screens, full Latin Extended for Kinyarwanda and French.
- **Barlow Condensed** digits: the meter counter only.

Self-hosted woff2, latin and latin-ext subsets (`src/assets/fonts/NOTICE.md`).

## 4. Patterns, depth, motion

- Imigongo patterns as CSS data-URI tiles: a zigzag band on hero cards (`.imigongo-band`) and a
  nested-diamond field (landing showcase, staff sign-in, sidebar foot). Accents only, never
  behind text.
- Soft two-step shadows; 18-26 px radii; the bottom bar floats.
- Motion: short entrances, springy presses, the meter counter rolling up on the landing page,
  bars growing into charts, a check-and-diamonds celebration when a bill is paid, a bell that
  rings once for new messages, a scan line on the camera guide. All of it stops with
  `prefers-reduced-motion`.
- Loading: the Mubazi spinner (a turning lake-blue ring around a breathing terracotta diamond)
  with words, `src/components/Progress/Progress.tsx`.

## 5. Screens

**Household (phone first):** landing with a live meter showcase; home with a greeting, one status
card for what to do now (pay, being checked, next reading date, read now), a banner when an
officer decides a reading, quick actions, a usage chart and the account (with phone alerts);
bills as card rows with status chips; bill with a big total; payment with a celebration;
messages with type icons; the camera with corner brackets and a scan line. Bottom bar: Home,
Bills, a raised diamond Read button, Messages; the header has a bell with a count.

**Staff (desktop first):** a deep lake-blue sidebar in both themes, a top bar with the date,
an overview with a welcome banner, four figures with icon tiles, open issues by type as a bar
chart, the review queue with the photo, and tables with sticky-feeling headers and hover rows.

## 6. Alerts

When an officer accepts or rejects a reading the household gets the SMS (as before), the banner
on home, the bell count, and a **phone alert** (web push) if they turned it on: backend
`app/services/push.py`, keys from `scripts/make_vapid_keys.py`, service worker `public/sw.js`.

## 7. Writing

No emojis. Sentence case. Kinyarwanda first; every new Kinyarwanda string is a draft listed in
`docs/i18n/kinyarwanda_review_mubazi_redesign.csv` (and `_push.csv`) for a native speaker.
