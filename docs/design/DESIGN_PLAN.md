# Design plan: frontend redesign v2

Branch: `feature/frontend-redesign-v2`, from `rebuilt-main` (d776deb, which includes
`feature/anomaly-detection`).
Status: **approved 09/10/2026**, with the decisions in section 7.

This plan follows `.claude/skills/wasac-frontend-design/SKILL.md`. It replaces the rejected
`feature/frontend-redesign`; nothing from that branch's styling carries over.

---

## 0. What exists today

**Stack:** Create React App (react-scripts 5), React 18, react-router-dom 6, CSS Modules plus two
global stylesheets (`styles/global.css`, `styles/typography.css`). No state library, no i18n, no
HTTP client.

**Routes** (`src/router/index.jsx`), all except `/` and `*` wrapped in `AppShell`
(SideNav on desktop, BottomNav on mobile, BottomNav hidden on `/submit/camera` and `/payment`):

| Route | Screen | Audience |
|---|---|---|
| `/` | Welcome | both (role choice) |
| `/home` | CustomerHome | household |
| `/submit/camera` | CameraCapture | household |
| `/submit/confirm` | ConfirmReading | household |
| `/submit/manual` | ManualEntry | household |
| `/bill` | BillDisplay | household |
| `/payment` | Payment | household |
| `/history` | BillHistory | household |
| `/account` | Account | household |
| `/officer` | OfficerMode | staff |
| `/officer/review` | AnomalyReview | staff |

**Shared components:** BottomNav, SideNav, Button, Card, InputField, LoadingState,
NetworkErrorBanner, PageHeader, ProgressStep, SkeletonLoader, StatusBadge.

**Current look:** cream background `#F5F2EE`, teal accent `#0D9488`, Plus Jakarta Sans, monospace
for data, pill status badges, identical rounded cards. This matches several of the brief's
"AI-design tells" and is replaced entirely.

### API calls

The current screens call **no API at all**. They read mock data from `src/data/*.js`. The only real
`fetch` calls are in `src/pages/_legacy_archive/`, hard-coded to `http://localhost:8000`.
The rejected `feature/frontend-redesign` branch changed CSS only and has no API code to reuse.

| Endpoint (backend) | Used by (legacy) | Notes |
|---|---|---|
| `POST /submit-photo` (multipart `file`) | CameraScreen | Returns `status` (`readable`/`unreadable`), `predicted_reading`, `confidence`, `quality_gate_score`, `guidance_message` |
| `POST /confirm-reading` `{customer_id, meter_id, confirmed_reading}` | ConfirmReading | Returns `success`, `bill_amount`, `consumption_m3`, `tariff_breakdown`, `validation_status`, `anomaly_flagged`, `bill_id`, `error_message` |
| `POST /bills/{bill_id}/pay` | PaymentScreen | MoMo is simulated client side (2 s delay, fake transaction ID) |
| `GET /customers` | OfficerMode | `CustomerInfo[]` |
| `GET /customers/{id}/bills` | not used yet | needed for usage history |
| `POST /calculate-bill`, `POST /submit-ussd`, `GET /health` | not used | |

**Only on `feature/anomaly-detection`, not on `rebuilt-main`:**
`GET /flags`, `PATCH /flags/{id}/resolve` `{outcome: "accept" | "reject"}`, `POST /score`, and
`ConfirmReadingResponse.anomaly` (with `pending_review`, `anomaly_type`, `message_for_household`,
`needs_retake`). The staff review queue and the household "held for checking" state depend on these.
Anomaly types: `MISREAD_SUSPECTED`, `SPIKE`, `SUSTAINED_HIGH`, `METER_STUCK`, `UNUSUAL`,
`BASELINE`, `NORMAL`. Readings are 8 digits, the last 3 being litres
(`ANOMALY_READING_LENGTH=8`, `ANOMALY_DECIMAL_DIGITS=3`), which is what the counter below is built on.

### Integration work the redesign will do

- One `src/api/client.js` with the base URL from `REACT_APP_API_URL`, timeouts, and a shared
  `{loading, failed, retry}` pattern. Screens stop importing from `src/data/`.
- Keep the photo in memory after a failed upload so "Try again" does not mean "take it again".
- Add a small `t()` helper and `src/i18n/{rw,en,fr}.json`, without a heavy library. Every string
  goes through it.

---

## 1. Colour

Taken from the meter: black and red number wheels, the brass body, the glass window.
Six values, no gradients, no dark mode.

| Name | Hex | Role | Contrast (checked) |
|---|---|---|---|
| **Wheel black** | `#000000` | Cubic-metre counter cells, primary buttons, body text | Paper on it 21:1 |
| **Litre red** | `#A3111F` | Litre counter cells. **Used nowhere else.** | Paper on it 7.9:1 |
| **Brass** | `#6E5414` | Counter bezel, "held for checking" status text and border | on Paper 7.1:1 (text allowed on Paper only; 5.9:1 on Glass) |
| **Slate** | `#454E4B` | Secondary text, labels, inactive nav | on Paper 8.6:1, on Glass 7.1:1 |
| **Glass** | `#E4EAE7` | Page background, the meter window behind the counter, quiet panels | Black on it 17.2:1 |
| **Paper** | `#FFFFFF` | Surfaces that hold reading and paying content, digits on counter cells | |

**State colours without new hues:**
- Paid / accepted: black text, check icon, Glass panel. No green.
- Held for checking: Brass text and 2px Brass border on Paper, clock icon. Calm, not alarming.
- Error: black text with a "!" icon right next to the field or action that failed, plus the fix in
  words. Not red, because red means litres.
- Focus: 3px Wheel black outline with a 2px Paper gap, so it shows on black buttons and white
  surfaces alike. Not Brass (2.9:1 on black fails).

**Why no dark mode:** the household app is used outdoors in sunlight, where a light theme with black
text reads best. Staff work in offices. Neither audience needs one; it would double the testing.

---

## 2. Type

Two families with clearly separate jobs. Self-hosted WOFF2, no Google Fonts CDN call
(one less DNS lookup on patchy data, works offline once cached).

| Family | Role | Why |
|---|---|---|
| **Atkinson Hyperlegible Next** (400, 700) | All interface text, amounts, dates, tables | Built for low-vision legibility: distinct `1 l I`, `0 O`, open counters. Readable on cheap screens in sun. Latin Extended covers French accents and Kinyarwanda. Tabular figures for amounts. |
| **Barlow Condensed** (600) | Counter digits only | Narrow, upright digits like the printed numbers on meter wheels. 8 digits fit at 360px. Subset to `0-9` only, so the file is a few KB. |

Fallbacks: `system-ui, "Segoe UI", Roboto, sans-serif` for the text face;
`"Arial Narrow", sans-serif-condensed, sans-serif` for the counter.
Before building: confirm `tnum` in the Atkinson Next files we ship. If missing, amounts get
`font-variant-numeric: tabular-nums` via the fallback stack and we note it.

**Scale** (Bringhurst's classical scale, px):

| Step | Size / line height | Use |
|---|---|---|
| small | 14 / 20 | Staff table secondary text, footnotes. Never for household body text. |
| body-staff | 16 / 24 | Staff dashboard body |
| body | 18 / 28 | Household body text and buttons |
| lead | 21 / 28 | Household screen headings, amounts in lists |
| title | 24 / 32 | Bill total, staff page titles |
| counter | 36 digits in 52px cells | Household counter (mobile); 48 in 68px cells at ≥ 600px |
| counter-small | 24 digits in 36px cells | Staff review pane |

Sentence case everywhere. No ALL-CAPS labels, no letter-spacing tricks. Body line length capped at
`60ch` for households, `75ch` for staff.

---

## 3. Layout

**Household concept:** one task per screen; the counter sits near the top the way the meter sits on
the wall, and the one action you need sits at the bottom under your thumb.

**Staff concept:** a review desk: queue on the left, and for the selected reading the photo, the
read digits and that household's last six months side by side, decided with the keyboard.

### Alignment rules

- 4px base grid. Household side gutter 16px, staff 24px.
- Household content is one column, max width 480px, centred on larger screens.
- Primary action is a full-width 56px button pinned to the bottom safe area. At most one primary
  action per screen; a secondary action is a plain text button above it.
- All numbers are right-aligned in lists and tables, with tabular figures, so units line up.
- Radii by object, not one radius everywhere: counter cells 3px (wheel windows), counter bezel
  10px, buttons 8px, panels 0px edge-to-edge on mobile and 8px on desktop.
- No drop shadows. Separation comes from Glass vs Paper, not shadows.

### Wireframe 1: household submit flow (360px)

Real sequence, so steps are shown as "Step 1 of 3" in words.

```
 Step 1 of 3: take photo          Step 2 of 3: check the numbers     Step 3 of 3 (held case)
┌──────────────────────────────┐ ┌──────────────────────────────┐ ┌──────────────────────────────┐
│ ←  Read your meter           │ │ ←  Check the numbers         │ │    Reading sent              │
│                              │ │                              │ │                              │
│ ┌──────────────────────────┐ │ │ ┌──────────────────────────┐ │ │  [clock] We're checking this │
│ │                          │ │ │ │ [photo of meter, cropped │ │ │  reading.                    │
│ │      live camera         │ │ │ │  to the number window]   │ │ │                              │
│ │                          │ │ │ └──────────────────────────┘ │ │  You don't need to do        │
│ │   ┌──────────────────┐   │ │ │                              │ │  anything. We'll text you    │
│ │   │ fit the numbers  │   │ │ │  Do these match your meter?  │ │  within 24 hours.            │
│ │   │ inside this box  │   │ │ │ ╔══════════════════════════╗ │ │                              │
│ │   └──────────────────┘   │ │ │ ║█0█2█8█1█3│▓4▓5▓0▓        ║ │ │ ╔══════════════════════════╗ │
│ │                          │ │ │ ╚══════════════════════════╝ │ │ ║█0█2█8█1█3│▓4▓5▓0▓        ║ │
│ └──────────────────────────┘ │ │   2,813.450 m³               │ │ ╚══════════════════════════╝ │
│                              │ │  Tap a number to change it.  │ │   sent 09/10/2026            │
│ Hold the phone still, about  │ │                              │ │                              │
│ one hand-length away.        │ │  ─ soft retake prompt, only  │ │                              │
│                              │ │    if quality is low:        │ │                              │
│  Upload a photo instead      │ │  "The last digits are blurry.│ │                              │
│ ┌──────────────────────────┐ │ │   Move closer and hold the   │ │                              │
│ │       Take photo         │ │ │   phone still."  Retake      │ │ ┌──────────────────────────┐ │
│ └──────────────────────────┘ │ │ ┌──────────────────────────┐ │ │ │      Back to home        │ │
└──────────────────────────────┘ │ │     Confirm reading      │ │ │ └──────────────────────────┘ │
                                 │ └──────────────────────────┘ │ └──────────────────────────────┘
 █ = Wheel black cell            └──────────────────────────────┘
 ▓ = Litre red cell                (not held → goes straight to the bill)
 ║ = Brass bezel
```

States on this flow: uploading ("Reading the numbers…"), upload failed ("We couldn't send the
photo. Check your data connection." + "Try again", photo kept), unreadable (guidance text from the
API + "Retake", never blocking: "Type the numbers instead" is always offered).

The retake prompt is advice only. "Confirm reading" stays enabled while the quality warning is
shown; "Retake" is a secondary text button next to the warning, never a gate.

### Wireframe 2: household bill (360px)

```
┌──────────────────────────────┐
│ ←  September bill            │
│                              │
│  You used 22.4 m³            │  ← lead size, plain text
│  14/08/2026 to 13/09/2026    │
│                              │
│  This reading                │
│ ╔══════════════════════════╗ │
│ ║█0█2█8█1█3│▓4▓5▓0▓        ║ │  ← counter, display only
│ ╚══════════════════════════╝ │
│  Last reading     2,791.050  │  ← plain tabular text, not a 2nd counter
│                              │
│ ┌──────────────────────────┐ │  Paper panel
│ │ Water          RWF 8,940 │ │
│ │ Service charge RWF 1,000 │ │
│ │ ──────────────────────── │ │
│ │ Total         RWF 9,940  │ │  ← title size, bold, right aligned
│ │ Pay by        30/09/2026 │ │
│ │                          │ │
│ │ How this is worked out ▸ │ │  ← expands tariff tiers
│ └──────────────────────────┘ │
│                              │
│  Your last 6 months          │
│  Apr ▇▇▇▇▇ 21                │  ← simple bar per month, m³,
│  May ▇▇▇▇▇▇ 23               │    current month in black,
│  ...                         │    others Slate
│  Sep ▇▇▇▇▇▇ 22               │
│ ┌──────────────────────────┐ │
│ │     Pay RWF 9,940        │ │  ← pinned, thumb reach
│ └──────────────────────────┘ │
└──────────────────────────────┘
```

Payment: phone number prefilled → "Pay RWF 9,940" → "Approve on your phone" waiting state with
"I didn't get a prompt" help → "Paid" with transaction ID and date. The button label changes from
"Pay" to "Paid"; nothing else is renamed.

### Wireframe 3: staff review queue (1280px)

```
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ WASAC billing   Review queue (12)   Flags   Households                     Signed in: J. Uwase│
├──────────────────────────┬────────────────────────────────────────────────────────────────────┤
│ Held readings      J / K │ Nzeyimana J-P · WAS-KIG-2018-03155 · Nyamirambo                     │
│                          │ Reading higher than usual          held 13/09/2026, 2 days ago     │
│▌Nzeyimana J-P            ├──────────────────────────┬─────────────────────┬───────────────────┤
│ Higher than usual  128 m³│ Meter photo              │ Read by the system  │ Last 6 months, m³ │
│                          │ ┌──────────────────────┐ │ ╔═════════════════╗ │ Apr   21          │
│ Hakizimana T.            │ │                      │ │ ║█0█1█9█7█1│▓0▓0▓0▓║│ May   23          │
│ Lower than last month 14 │ │   photo, zoomable    │ │ ╚═════════════════╝ │ Jun   19          │
│                          │ │   (Z to zoom)        │ │ Previous  1,843.000 │ Jul   24          │
│ Ingabire S.              │ │                      │ │ Used        128 m³  │ Aug   22          │
│ Photo unclear       87 m³│ └──────────────────────┘ │ Usual       ~22 m³  │ Sep  128  ◀ this  │
│                          │                          │ Confidence    61 %  │                   │
│ …                        │                          │                     │ 5.8× usual        │
│                          ├──────────────────────────┴─────────────────────┴───────────────────┤
│                          │ [ Accept reading  A ]   [ Reject, ask for retake  R ]   Skip  S    │
│                          │ Accepting creates a bill for RWF 118,420.                          │
└──────────────────────────┴────────────────────────────────────────────────────────────────────┘
 ▌ = selected row (black bar + bold, not colour alone)
```

Keys: `J`/`K` next/previous, `A` accept, `R` reject, `S` skip, `Z` zoom photo, `?` shows the list.
After a decision the next reading loads in place; a 5-second "Undo" line replaces the action bar.
Staff copy maps codes to plain words: `SPIKE` → "Higher than usual", `MISREAD_SUSPECTED` →
"Lower than last month" or "Photo unclear" (by feature), `METER_STUCK` → "Same reading for N days",
`SUSTAINED_HIGH` → "High for several months".

At < 1024px the three panes stack (photo, digits, history) with the action bar sticky at the
bottom; staff on laptops keep everything above the fold at 1366×768.

---

## 4. Signature: the meter counter

A `<MeterCounter>` component that shows a reading the way the wall meter shows it.

- 8 cells: 5 cubic-metre cells in Wheel black, then 3 litre cells in Litre red, digits in Paper,
  Barlow Condensed 600, tabular. A 2px gap between cells, a 6px gap plus a thin Paper divider
  between m³ and litres (where the decimal point is).
- Brass bezel (3px) around the cells on a Glass window. That is the only ornament.
- Leading zeros are shown, as on the meter (`02813` not `2813`).
- Screen readers get one value: "2,813.450 cubic metres", not eight digits.
- Edit mode (confirm screen only): one real `<input inputmode="numeric">` laid over the cells, so
  typing, paste and voice input work; the cell under the caret gets the focus ring.
- At 360px: 36px digits in 34×52px cells, total width ≈ 310px, inside the 328px content width.
- No rolling animation. With reduced motion off, a single digit change on edit may slide 4px once;
  that is the only motion in the app.

**Where it is used:**
1. Confirm reading (editable).
2. "Reading held for checking" state (display).
3. Bill: "This reading" (display, once).
4. Staff review pane, small size (display).

**Where it is NOT used:**
- Money. RWF amounts are always plain text, so a price never looks like a volume.
- Consumption ("22.4 m³"), averages, and history lists: plain tabular numbers.
- Previous reading on the bill: plain text, so there is one counter per screen.
- Staff queue rows and tables: plain text. The counter appears only in the decision pane.
- Home, notifications, account, navigation, empty states, loading states, icons.

---

## 5. Principles

1. **The screen matches the wall.** Digits appear in the same order, grouping and colours as on the
   household's meter, so checking a reading is a glance from the wall to the phone.
2. **Volume is a counter, money is a sentence.** m³ readings use the counter; RWF is always plain,
   bold text. They never share a style.
3. **Nobody is accused.** A held reading is "being checked", never "suspicious" or "anomaly". Brass,
   not red. The household is told what happens next and when.
4. **A dropped connection loses nothing.** Every network action has loading, failed and retry
   states; the photo and typed digits survive a failure and a page reload.
5. **Staff decide on one screen.** Photo, digits and history are visible together; every decision
   has a key and an undo.

---

## 6. Checked against the brief: what I changed

For each first instinct I asked "would I do this for any other utility app?" These failed and were
revised.

| First idea | Problem | Revised to |
|---|---|---|
| Keep a teal accent for buttons and links | Teal/blue utility look; nothing to do with the meter | Primary buttons in Wheel black. No accent hue apart from the meter's own red and brass. |
| Red for errors and the reject button | Red already means "litres". Using it for errors dilutes the counter and makes staff "reject" look like a household mistake | Red appears only in litre cells. Errors are black text + icon + fix. Reject is an outlined black button with its label and key. |
| Brass for primary buttons | Every button would become part of the signature; brass on black fails as a focus ring | Brass only on the counter bezel and the "held" state. |
| Home screen led by a big counter of the last reading with a small label | That is tell #6 (big number + small label hero) and it shows an old number before the user has done anything | Home leads with what to do next ("Take meter photo", or "Pay RWF 9,940 by 30/09/2026"), in words. |
| Glassy gradient and inner shadow over the counter to look like a real window | Decorative; costs paint time on cheap phones; a "designed" flourish | Flat Glass background behind the cells. |
| Counter used for the previous reading as well, two counters on the bill | Two counters compete; the bill is about money | One counter per screen; previous reading as plain text. |
| Staff queue as a full-width table with hairline rules | Tell #3 (broadsheet) and forces a second screen for the photo | Queue rail plus a three-pane decision area. |
| Meter IDs and account numbers in monospace | Tell #5 | Atkinson Hyperlegible Next with tabular figures. |
| "01 / 02 / 03" step markers | Tell #7 style; fine as a sequence but numbers-as-decoration | "Step 2 of 3" in words, which also translates. |
| Dark mode for staff | Not justified by their office setting; doubles QA | Light only. |
| Load fonts from Google Fonts | Extra lookup and request on patchy data | Self-hosted, Barlow subset to digits only. |

---

## 7. Decisions (09/10/2026)

1. **Anomaly endpoints.** `feature/anomaly-detection` is merged into `rebuilt-main` (46 backend
   tests pass) and this branch is rebased onto it. Staff screens use the real `/flags` and
   `/flags/{id}/resolve`, not mocks.
2. **Base.** 2ced262 is pushed; `rebuilt-main` is now d776deb, which also tracks the skill.
3. **Translations.** English is filled in. Every Kinyarwanda and French string is
   `"TODO: translate"` for review by the product owner. No machine translation of Kinyarwanda.
4. **Counter input.** The counter is always 8 digits (5 m³ + 3 litres). The CRNN is not connected
   yet, so the frontend is built against the `/submit-photo` response shape only, and handles what
   the CRNN is known to do:
   - readings shorter than 8 digits are left-padded with zeros (`565846` → `00565846`);
   - anything that still is not 8 digits (too long, non-digits, empty) opens the editable
     "check the numbers" state instead of an error.

## 8. Build order

Tokens as CSS custom properties → base typography → `MeterCounter` →
**checkpoint: counter screenshots at 360px and desktop, display and edit mode, plus a short
reading, approved before any screen is built** → API client and i18n → household screens
(camera, confirm, held, bill, pay, history, home, notifications) → staff screens (review queue,
flags, household detail). One screen per commit, each with screenshots at 360px and desktop width,
and one decorative element removed before it is called done. The branch is not merged into
`rebuilt-main`; it is reviewed by the product owner.
