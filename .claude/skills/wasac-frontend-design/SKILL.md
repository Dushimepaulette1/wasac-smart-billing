WASAC Smart Water Billing - Frontend Design

You are the design lead for this product. The client has chosen a clear visual direction: a calm, premium, professional look built on deep navy-to-blue gradients and elegant serif headlines (reference: a dark blue glowing gradient page with a large serif headline, short sans-serif body, a thin outlined button, and generous empty space). Follow that direction exactly, and adapt it to a water billing product used by real households in Rwanda.
1. Know the product before designing

What it does: a household photographs its water meter, the system reads the digits, checks the reading against that household's own history, creates a bill, and the household pays with MTN Mobile Money. Suspicious readings are held for WASAC staff to accept or reject.

Two audiences, two different interfaces:

| | Household app | WASAC staff dashboard | |---|---|---| | Who | Residents of Kigali and other towns, all ages and literacy levels | Billing and field staff | | Device | Low-cost Android phone, often outdoors in bright sun, patchy mobile data | Laptop or desktop in an office | | Job | Submit a reading in under a minute, understand the bill, pay | Review held readings fast and fairly, spot leaks and misreads | | Feel | Calm, premium, plain, impossible to get lost | Professional, dense, keyboard-friendly |

Key screens:

    Public: landing page (what the service is, start a reading, staff sign-in).
    Household: take/upload meter photo -> soft retake prompt (never blocking) -> confirm the reading -> "reading held for checking" -> bill -> pay with MoMo -> usage history -> messages.
    Staff: review queue of pending_review readings -> anomaly flags -> household detail.

2. Visual direction
The world: deep water at night

    Background: deep navy fading into luminous mid-blue glows, like the reference. Built with layered CSS radial-gradients on a near-navy base. No filter: blur(), no canvas, no video, no animated gradients - cheap phones must render it instantly. One static gradient composition per page type is enough.
    Headlines: an elegant, high-contrast serif in white or near-white, large and confident, usually two short lines. This is where the personality lives.
    Body text: a highly legible sans-serif, smaller and quiet, in light blue-grey on dark areas.
    Buttons: primary = solid light button with dark text (strong contrast for the one key action); secondary = thin outlined pill like the reference. Never a glowing or gradient button.
    Space: generous. Few elements per screen. Centre-aligned hero on the landing page; left-aligned content inside the app.

Readability rule: content lives on light panels

The household app is used outdoors in sunlight, where white text on dark blue is hard to read. So: the dark gradient is the stage, and anything a person must read carefully - the reading, the bill, amounts, forms, payment, error messages - sits on a light panel (off-white with a faint blue tint) floating on the gradient, with dark text. Short headlines and navigation may sit directly on the dark background. The staff dashboard may be darker overall (office lighting), but data tables and the decision pane still use light or high-contrast surfaces.
Signature element: the meter counter

Wherever a reading appears, show it as a meter counter: each digit in its own cell, cubic-metre digits on black cells, litre digits on red cells, tabular figures. On the navy background this is the one element that says "this is a water meter, this is WASAC". Keep it. Use it only on: confirm reading, held state, bill ("this reading"), staff decision pane. Never for money or history lists.
Colour (refine exact values in the design plan, check contrast)

    Deep navy (page base), mid blue (gradient glow), pale ice blue (glow highlights)
    Off-white panel surface, ink (near-black text on panels)
    Meter black and meter red (counter only - red is used nowhere else, including errors)
    One calm warm tone for the "held for checking" state (e.g. brass/amber), never alarming red

Still avoid

    Water droplet icons, wave SVGs, bubbles, splash illustrations, stock photos of taps or families.
    Neon/acid accents, glassmorphism blur, glowing borders, gradient text.
    SaaS card kit: identical rounded cards with the same soft grey shadow everywhere.
    Template chrome: ALL-CAPS tracked eyebrow labels above every heading (the reference has one small eyebrow on the hero only - at most one per page), meta text joined with middle dots, monospace for data labels, "->" appended to buttons.
    Numbered markers (01/02/03) on content that is not a real sequence.
    Fade-and-slide-up animation on every section. At most one orchestrated moment (landing hero).

3. Hard constraints (non-negotiable)

Household app:

    Mobile first at 360px, no horizontal scrolling.
    Text on panels: WCAG AA minimum, aim for AAA on readings and amounts. Text directly on the gradient: check contrast against the lightest part of the gradient behind it.
    Tap targets at least 48x48px; primary action within thumb reach at the bottom.
    Low bandwidth: no hero images, no video, no icon fonts, no heavy animation libraries. Self-host fonts, at most three families (serif display, sans body, counter digits), subset where possible.
    Every network action has loading, failed and retry states; photos and typed digits survive a failure.
    Money: "RWF 4,500" (whole francs). Dates: DD/MM/YYYY. Volumes: "12.4 m3".

Staff dashboard: keyboard-driven review queue (next/previous, accept, reject, undo); photo, read digits and household history side by side; tabular figures for all numbers.

Both: visible keyboard focus, reduced motion respected, colour never the only signal, semantic HTML, pinch-zoom allowed. Do not copy the official WASAC logo unless approved assets are in the repo.
4. Language: Kinyarwanda first

    Use react-i18next (with i18next). Kinyarwanda (rw) is the default language, English (en) is the fallback, French (fr) is available.
    Every user-facing string goes through t(). No hard-coded text, no text inside images.
    The language choice is remembered on the device and switchable from the header and home screen.
    Kinyarwanda text is often longer than English: design for strings up to 50% longer; never truncate a sentence.
    Never machine-translate Kinyarwanda into the app. Missing strings fall back to English and are listed for the client to write.

5. Typography

    Display: an elegant high-contrast serif with good Latin Extended support (evaluate options such as Cormorant Garamond, Fraunces or EB Garamond against the reference; pick one, justify it). Use it only for headlines and large statements, never for body text, forms or numbers.
    Body: Atkinson Hyperlegible Next (legibility on cheap screens, tabular figures).
    Counter digits: Barlow Condensed, subset to 0-9.
    Clear type scale (The Elements of Typographic Style), body line length under 80 characters, sentence case everywhere.

6. Writing in the interface

    Plain verbs, sentence case, active voice, no filler, no marketing slogans.
    Buttons say exactly what happens: "Take photo", "Confirm reading", "Pay RWF 4,500".
    Retake prompts are specific and kind: "The last digits are blurry. Move closer and hold the phone still."
    Held readings never accuse: "We're checking this reading. You don't need to do anything."
    Errors say what went wrong and how to fix it, never apologise, never vague.
    Staff copy is plain: "Reading lower than last month", not "MISREAD_SUSPECTED".

7. Engineering conventions

    React + TypeScript (strict mode). Typed API client and typed response models matching the FastAPI schemas; no any without a comment explaining why.
    CSS Modules plus design tokens as CSS custom properties. Keep selector specificity flat.
    Tests with React Testing Library; keep all existing tests passing through every change.

8. Process: plan, check, build, critique

    Inspect the existing code first; keep all API behaviour working.
    Update docs/design/DESIGN_PLAN.md for this direction: palette with hex values and contrast checks, type choices, gradient recipe, ASCII wireframes for the landing page, bill screen and staff review queue, and how the counter and light panels sit on the gradient.
    Check every choice against this brief; write down what you changed and why.
    Stop and show the plan. No UI code until it is approved.
    Build one screen per commit, screenshot at 360px and desktop, remove one decorative element that does not serve the user before calling a screen done.

9. Restraint

The gradient sets the mood, the serif headline gives the voice, the counter gives the identity. Everything else is quiet. If a choice exists only to look "designed", cut it.