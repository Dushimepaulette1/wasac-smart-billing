---
name: wasac-frontend-design
description: Design direction for the WASAC Smart Water Billing Platform frontend (React). Use whenever building, redesigning or restyling any screen, component, colour, typography or copy in the frontend, for the household app or the WASAC staff dashboard.
---

# WASAC Smart Water Billing - Frontend Design

You are the design lead for this product. The previous redesign was rejected because it looked
generic and AI-made. The client wants an interface that could only belong to this product:
a water billing platform for households in Rwanda, built around a photo of a physical water meter.
Make deliberate, specific choices. Do not fall back on defaults.

## 1. Know the product before designing

**What it does:** a household photographs its water meter, the system reads the digits, checks
the reading against that household's own history, creates a bill, and the household pays with
MTN Mobile Money. Suspicious readings are held for WASAC staff to accept or reject.

**Two audiences, two different interfaces:**

| | Household app | WASAC staff dashboard |
|---|---|---|
| Who | Residents of Kigali and other towns, all ages and literacy levels | Billing and field staff |
| Device | Low-cost Android phone, often outdoors in bright sun, patchy mobile data | Laptop or desktop in an office |
| Job | Submit a reading in under a minute, understand the bill, pay | Review held readings fast and fairly, spot leaks and misreads |
| Feel | Calm, plain, trustworthy, impossible to get lost | Dense, efficient, keyboard-friendly |

Design them as two related but distinct experiences. Do not force the dashboard's density onto
households or the households' simplicity onto staff.

**Key screens:**
- Household: take/upload meter photo -> retake prompt (soft, never blocking) -> confirm the
  reading -> "reading held for checking" state -> bill -> pay with MoMo -> usage history ->
  notifications (possible leak, retake requested).
- Staff: review queue of `pending_review` readings (photo, read digits, household history,
  anomaly type, accept/reject) -> anomaly flags list -> household detail with consumption history.

## 2. Where the visual identity comes from

Take distinctive choices from the real world of this product, not from "water app" clichés.

**The signature element is the meter counter itself.** A real WASAC meter shows rolling wheels:
black wheels for cubic metres, red wheels for litres. Wherever a reading appears, it may be shown
as a counter: each digit in its own cell, cubic-metre digits on dark cells, litre digits on red
cells, tabular figures so digits never shift. This links what the household sees on screen to what
they see on their wall. Spend the design's boldness here. Keep everything around it quiet.

Other honest sources of material: the meter's glass and brass body, pipes and valves, the
household's own consumption over time, Rwandan francs, the moment of paying with a phone.

**Clichés to avoid for this subject:**
- Water droplet icons, wave SVGs, bubbles, "splash" illustrations.
- Blue-to-cyan gradients and an all-blue palette.
- Stock photos of taps or smiling families.
- Generic utility-company look: blue header, white cards, grey shadows.

**General AI-design tells to avoid** (unless I explicitly ask for one):
1. Warm cream background (~#F4F1EA) with a high-contrast serif and a terracotta/clay accent (~#D97757).
2. Near-black background with one acid-green or vermilion accent.
3. Broadsheet layout: hairline rules, zero radius, dense newspaper columns.
4. SaaS card kit: everything in identical rounded cards, same radius everywhere, the same soft grey
   shadow (rgba(0,0,0,.1)), decorative gradient washes.
5. Template chrome: tracked-out ALL-CAPS eyebrow labels above headings, meta text joined with
   middle dots, "Word - fragment" labels, #0B0B0B/#111 instead of real black, monospace for small
   data labels, "->" appended to buttons.
6. A big number with a small label plus a gradient accent as the default "hero".
7. Numbered markers (01/02/03) on content that is not a real sequence. (Submitting a reading IS a
   real sequence, so steps there are fine.)
8. Fade-and-slide-up animation on every section, hover effects on every card.

## 3. Hard constraints (non-negotiable)

**Household app:**
- Mobile first: design at 360px wide first, then scale up. No horizontal scrolling.
- Readable in direct sunlight: text contrast at least WCAG AA, aim for AAA on readings and amounts.
- Tap targets at least 48x48px. Primary actions within thumb reach at the bottom of the screen.
- Low bandwidth: no hero images, no video, no icon fonts, no heavy animation libraries. Load at most
  two font families, subset to Latin plus Latin Extended, with good system fallbacks.
- Works with slow or dropped connections: every network action has loading, failed and retry states.
- Three languages: Kinyarwanda, English, French. Leave room for text up to 40% longer than English.
  Never put text inside images.
- Money: Rwandan francs, no decimals, e.g. "RWF 4,500". Dates: DD/MM/YYYY. Volumes: "12.4 m3"
  (show litres only where they matter).

**Staff dashboard:**
- Built for speed: the review queue must be usable with the keyboard (next/previous, accept, reject).
- Show the meter photo, the read digits and the household's recent history side by side, so a
  decision never needs a second screen.
- Dense but calm: clear hierarchy, aligned numbers, tabular figures for all amounts and readings.

**Both:**
- Visible keyboard focus, reduced motion respected, colour never the only signal (pair with text or
  an icon), semantic HTML.
- Do not copy the official WASAC logo or brand assets unless the repo already contains approved
  versions. Use the name in text only.

## 4. Typography

- One or two families. If two, make them clearly different in role.
- Choose deliberately, not the usual defaults (no Inter, Roboto, Poppins, Montserrat, Open Sans,
  Space Grotesk unless strongly justified for this brief).
- Requirements: excellent legibility at small sizes on cheap screens, tabular numerals, full Latin
  Extended support for Kinyarwanda and French.
- Good starting points to evaluate (not mandates): Atkinson Hyperlegible (designed for low-vision
  legibility) for body text; a condensed grotesque such as Barlow Condensed for counter digits,
  echoing the narrow digits on real meter wheels.
- Set a clear type scale (follow The Elements of Typographic Style), body line length under 80
  characters, sentence case everywhere.

## 5. Writing in the interface

Words exist to help a person finish a task. Write for a household member who is not technical.

- Plain verbs, sentence case, active voice, no filler, no marketing.
- A button says exactly what happens: "Take photo", "Confirm reading", "Pay RWF 4,500".
  The same action keeps the same name through the flow ("Pay" -> "Paid").
- Retake prompts are specific and kind: "The last digits are blurry. Move closer and hold the phone
  still." Not "Image quality insufficient."
- Held readings never accuse the household: "We're checking this reading. You don't need to do
  anything. We'll text you within 24 hours." Not "Anomaly detected."
- Leak alerts are useful: what was noticed, what to check, what happens next.
- Errors say what went wrong and how to fix it. Errors don't apologise and are never vague.
- Empty screens invite the next action ("No readings yet. Take your first meter photo.").
- Staff copy can be more technical but still plain: "Reading lower than last month",
  not "MISREAD_SUSPECTED".
- All user-facing strings go through the translation files, never hard-coded.

## 6. Process: plan, check, build, critique

1. **Inspect first.** Read the existing frontend: framework, routing, styling approach, components,
   API calls. Keep all API integration and behaviour working; this is a visual and UX redesign.
2. **Write a design plan** in `docs/design/DESIGN_PLAN.md`:
   - Colour: 4-6 named hex values with their roles, plus a dark mode only if justified.
   - Type: families, roles, type scale.
   - Layout: one-sentence concept per audience, ASCII wireframes for 3 key screens
     (household submit flow, household bill, staff review queue), alignment rules.
   - Signature: exactly how the meter counter is used, and where it is NOT used.
   - Principles: 3-5 rules specific to this product.
3. **Check the plan against this brief.** For each choice ask: would I make the same choice for any
   other utility app? If yes, revise it and write down what changed and why.
4. **Stop and show me the plan.** Do not write UI code until I approve it.
5. **Build in order:** design tokens as CSS custom properties -> base typography -> the counter
   component -> household screens -> staff screens. One screen per commit.
6. **Critique as you go.** Check each screen at 360px and at desktop width. Take screenshots if the
   environment allows. Before calling a screen done, remove one decorative element that does not
   serve the user.
7. Keep CSS specificity simple and predictable; avoid type selectors and class selectors fighting
   over spacing.

## 7. Restraint

One memorable thing (the counter), everything else disciplined. If a choice exists only to look
"designed", cut it.
