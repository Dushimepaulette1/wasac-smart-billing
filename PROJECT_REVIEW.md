# WASAC Smart Water Billing: project review

Review date: 22 October 2026. This is a review of the local source, not a certification of a live deployment. No application code was changed. See [FILE_REVIEW.md](FILE_REVIEW.md) for the inventory and comments on individual files.

## Overall understanding

This is a household self-service water-meter reading and billing platform, with a separate staff operations area. Its core idea is to reduce manual meter-reading work while keeping a person involved when an automated reading is questionable.

A household signs in with its registered phone number and an SMS code, chooses a meter if necessary, and takes or uploads a photograph. YOLO locates the number window; image checks and a MobileNetV2 classifier offer guidance; a ResNet18 + bidirectional GRU reader decodes the digits using CTC. The household confirms or corrects eight wheels: five for cubic metres and three for litres. For example, `00565846` represents **565.846 m³**.

The backend compares the confirmed cumulative reading with the meter's previous reading and household history. Rules, and an Isolation Forest when an artifact is available, identify suspicious readings or unusual consumption. Some readings are billed immediately; others wait for a staff decision. Staff have an overview, household search, review queue, activity log, account management, and password changes.

**My assessment:** a substantial, thoughtfully designed capstone prototype with an unusually complete household-to-staff workflow. Its main weakness is the gap between a convincing interface and the guarantees needed for real billing. Prioritize correctness and operational integration before adding screens or changing frameworks.

## Features found in the current implementation

| Area | Implemented capability | Qualification |
|---|---|---|
| Household identity | SMS code login, 30-day tokens, account ownership checks, multiple accounts per phone | Delivery depends on SMS configuration; demo codes can be displayed |
| Camera | Rear camera, uploads, image resizing, live hints, automatic capture, data-saving switch | Camera and location behavior still needs physical-device testing |
| Reading | Real model adapters for PyTorch and ONNX; crop preview; editable eight-digit counter | Weights are external artifacts; loaded state is not guaranteed by code existing |
| Recovery | Photo/digit draft storage, retry screens, timeout and offline messages | There is no durable offline synchronization queue |
| Anomalies | Backward-reading, high-use, stuck-meter and location checks; household-relative model features | More advanced classifications depend on a trained artifact and sufficient history |
| Staff review | Accept/reject pending readings, history context, keyboard shortcuts, five-second undo window | Original photo is not retained; follow-up-only flags have a UI action mismatch |
| Bills | Tier calculation, amount, status, recent bills and usage bars | Repeated submissions create bills; period policy is missing |
| Payments | Payment screen and simulated paid status/transaction reference | No actual Mobile Money collection or reconciliation |
| Messages | Anomaly explanations, leak advice, review outcome, unread badge | Read state is device-wide; SMS delivery is not durable |
| Staff security | Officer/supervisor/admin roles, salted password hashes, lockout, activity log | Password changes do not revoke existing tokens |
| Accessibility and language | Kinyarwanda/English, semantic controls, focus handling, reduced motion, light/dark themes | Translation completeness is not linguistic validation; no French in current implementation |
| Deployment | Docker API, Render blueprint, Vercel SPA routing, checksummed model downloads | Configuration files are not proof of successful live deployment |

## What is good

1. **The workflow makes sense.** Photo quality advice does not trap the household; confirmation is always part of reading; questionable submissions can wait for staff without corrupting the meter baseline.
2. **The code has useful boundaries.** API routes, database models, schemas, billing, anomalies, and vision are separate. Frontend networking, loaders, state, pages, and components are also separated. A larger rewrite is unnecessary.
3. **The interface reflects the task.** The physical-meter counter, litre distinction, plain bill amounts, retry messages, and separate staff workspace all serve actual user needs. The two inspected screenshots show a coherent visual system; they are historical evidence, not a current browser test.
4. **There is meaningful security work.** Household ownership is checked server-side, unauthorized account lookups return 404, passwords use salted PBKDF2, SMS codes use keyed hashes, demo accounts are marked, and secrets/weights are excluded from git and Docker.
5. **There is useful engineering around the ML.** Shared preprocessing, model checksums, ONNX adapters, parity tests, calibration scripts, held-out evaluation, and explicit limitations are stronger than simply calling a model from a route.
6. **The research notes are candid.** Calibration acknowledges optimistic training-set results and disables the blur rule when it performs poorly. Keep this honesty in the capstone presentation.
7. **Tests cover behavior.** Ownership checks, review states, anomaly rules, failure states, SMS redaction, upload limits, and digit conversion have meaningful coverage. The most serious remaining gaps are interactions between layers and concurrency.

## Findings to fix first

### 1. High: USSD bypasses household authentication

Evidence: [backend/app/api/routes/ussd.py](backend/app/api/routes/ussd.py:12).

`/submit-ussd` accepts caller-supplied JSON containing a phone number and reading, looks up that number, and invokes the same reading/billing service without authentication or provider verification. Anyone who knows a registered number can attempt submissions for it. It also returns account-dependent information. The optional session ID is unused.

**Recommendation:** restrict or disable this endpoint until it has a verified provider boundary, real session/menu handling, input normalization, rate limits, and an explicit multi-meter choice. Its existing JSON wrapper should be described as a prototype adapter, not a completed telecom integration.

### 2. High: readings and review decisions need idempotency and concurrency protection

Evidence: [backend/app/anomaly/service.py](backend/app/anomaly/service.py:180), [backend/app/anomaly/review.py](backend/app/anomaly/review.py:31), [backend/app/models/bill.py](backend/app/models/bill.py:12).

Every accepted submission creates a reading and bill. There is no request idempotency key or meter lock. A retry of an identical reading can create another bill with zero consumption and another RWF 1,000 service charge. Separate concurrent requests can also read the same old baseline. The one-to-one ORM relationship does not enforce a unique bill per reading in the database.

**Recommendation:** add a persisted idempotency key, a database uniqueness constraint for one bill per reading, and atomic meter/review updates. Test simultaneous submissions and simultaneous staff decisions against PostgreSQL.

### 3. High: monthly billing policy is absent

Evidence: [backend/app/services/billing.py](backend/app/services/billing.py:39), [backend/app/anomaly/service.py](backend/app/anomaly/service.py:242), [frontend/src/i18n/locales/en.json](frontend/src/i18n/locales/en.json).

The interface describes monthly tiers and a monthly service charge, but the implementation resets tariff tiers and charges the service fee for each bill-producing submission. Two readings in one month are not reconciled into one billing period. Splitting consumption into submissions can change the tariff charged.

**Recommendation:** explicitly model billing periods, opening/closing readings, tariff version, service-charge policy, adjustments, and rounding. Decide which readings are observations and which close a bill. Verify the tariff and tax policy with the project owner; this review did not independently establish the official tariff.

### 4. High for real use: payment success is simulated

Evidence: [backend/app/api/routes/billing.py](backend/app/api/routes/billing.py:92), [frontend/src/pages/Payment/Payment.tsx](frontend/src/pages/Payment/Payment.tsx).

The endpoint sets `payment_status = "paid"` immediately and constructs `MOMO-...` from the bill ID. There is no provider request, verified success, payment ledger, callback, or reconciliation. User-facing copy nevertheless says Mobile Money and "You paid".

**Recommendation:** label simulation clearly for the demo. Before real use, persist payment attempts with provider references, implement pending/success/failure states, verify provider responses, and reconcile outcomes idempotently. Settle a bill only on verified success.

### 5. High: the staff overview can silently report false zero debt

Evidence: [frontend/src/staff/loadOverview.ts](frontend/src/staff/loadOverview.ts:28), [frontend/src/api/client.ts](frontend/src/api/client.ts:102).

The overview uses staff authentication for customer/queue/flag calls, then calls `api.getBills`, which defaults to the household session. A staff-only browser therefore gets unauthorized bill requests. Every such error is converted to `[]`, and the overview computes zero unpaid bills. A browser with a household session can produce partial results instead.

**Recommendation:** make the auth context explicit for staff bill calls, and render failed totals as unavailable. Prefer one server-side overview endpoint with aggregates and pagination. Also remove the 12-most-recent-bills limit from debt calculations; older unpaid bills currently disappear from that calculation even after fixing authentication.

### 6. High: some review queue items cannot be resolved through the UI

Evidence: [backend/app/api/routes/anomaly.py](backend/app/api/routes/anomaly.py:106), [backend/app/anomaly/review.py](backend/app/anomaly/review.py:62), [frontend/src/pages/staff/ReviewQueue.tsx](frontend/src/pages/staff/ReviewQueue.tsx).

The queue includes all open flags requiring staff review, including already-billed `METER_STUCK`, `SUSTAINED_HIGH`, and `UNUSUAL` readings. The frontend only offers accept/reject, while the backend returns 409 for an outcome on a non-pending reading. The frontend client has no close-without-outcome operation. Household waiting checks also treat any staff follow-up flag as a held reading and can hide the next-reading action after an already-billed anomaly.

**Recommendation:** distinguish pending validation from follow-up work in the API. Show accept/reject only for pending readings and a close/follow-up action for billed flags. Derive household waiting status from the reading's actual status.

### 7. High: validate numeric input before persistence

Evidence: [backend/app/schemas/reading.py](backend/app/schemas/reading.py:67), [backend/app/api/routes/readings.py](backend/app/api/routes/readings.py:93), [backend/app/api/routes/ussd.py](backend/app/api/routes/ussd.py:32), [backend/app/schemas/billing.py](backend/app/schemas/billing.py:27).

Reading inputs are strings converted with `float()`. Python accepts `nan`, `inf`, and exponent notation; numeric fields also lack explicit finite-value constraints. The API does not enforce the eight-wheel range or three-decimal precision at its write boundary. Malformed values can reach calculations and database/response failures. Frontend validation does not protect a public API.

**Recommendation:** use a finite constrained decimal or integer litres, enforce meter capacity and permitted precision, and distinguish malformed negative input from a valid lower cumulative reading that needs review. Validate tariff inputs at the schema boundary too.

### 8. Medium/high: the review workflow lacks its original evidence

Evidence: [backend/app/models/reading.py](backend/app/models/reading.py), [backend/app/api/routes/readings.py](backend/app/api/routes/readings.py), [frontend/src/pages/staff/ReviewQueue.tsx](frontend/src/pages/staff/ReviewQueue.tsx:122).

Photo analysis and confirmation are unrelated requests: no server-side submission ID binds the image/model result to the final reading. The photo/crop remains in browser draft state and is cleared after success. Reader confidence and quality columns exist but are not populated by the confirmation service. Staff see history and digits but cannot inspect the photograph that caused the problem.

**Recommendation:** persist a submission record that links image/crop, model version and outputs, edits, location, customer, final reading, and reviewer decision. Give authorized reviewers a photo view with an explicit retention period. Treat client-supplied location as advisory, as the current code correctly does.

### 9. Medium: password changes do not revoke sessions

Evidence: [backend/app/core/security.py](backend/app/core/security.py:47), [backend/app/api/deps.py](backend/app/api/deps.py:28), [backend/app/api/routes/staff_auth.py](backend/app/api/routes/staff_auth.py:103).

Tokens contain only subject and expiry. Changing or resetting a password changes the hash but not the validity of an already-issued token. Temporary passwords are ordinary reusable passwords and are not forced to change on first use. Deactivating an account does block its current tokens, which is good.

**Recommendation:** use a session record or token version, revoke sessions after password reset, and persist a required-password-change flag. Keep account deactivation checks server-side.

### 10. Medium: drafts and message-read state are not scoped to an account

Evidence: [frontend/src/household/submission.tsx](frontend/src/household/submission.tsx:13), [frontend/src/household/session.tsx](frontend/src/household/session.tsx), [frontend/src/household/status.ts](frontend/src/household/status.ts:25).

One global draft is retained across household sign-out and meter switching. The draft has no owning meter/customer. Another signed-in account on the same tab can encounter the previous photo/digits and submit them against its currently selected meter. The messages-seen timestamp is also shared across accounts, and the navigation flag hook does not reload when the account changes.

**Recommendation:** bind drafts, caches, and read timestamps to customer/meter IDs; clear or explicitly preserve the right draft on account changes; test a multi-meter household and two households sharing a device.

## Further improvements

- **Immutable bill details:** `loadBill.ts` reconstructs tariff lines from the current calculator rather than returning the stored bill breakdown. Add a bill-detail endpoint with its actual reading, period, rate version, charges, amount and payment ledger. Otherwise a future tariff change can contradict old bill totals.
- **Training data integrity:** `scripts/_data.py::load_histories_db` selects all readings, including pending/rejected rows, unlike runtime scoring. Filter training history to confirmed statuses and record provenance. A meter replacement also needs an explicit baseline boundary so later feature calculations do not interpret the reset as negative consumption.
- **ML evidence:** the recorded result is 55.7% reading accuracy on 79 photos grouped into 34 inferred meters, with a wide 42–69% interval. Notebook reading accuracy ignores leading zeros; it is not strict eight-character exact match. Grouping is inferred from reading values, not verified meter IDs. Publish these qualifications alongside the result and evaluate new field photos with real meter IDs. The calibration document also records many incorrect readings without a CHECK_NUMBERS warning. Human confirmation must remain.
- **Notification durability:** SMS returns a delivery-acceptance boolean, but anomaly dispatch mostly ignores it and records `sms_household_logged` even on failure. Use a transactional outbox, background retries, and a distinction between queued, accepted, delivered and failed. Staff decisions and their audit entries should commit atomically; currently resolution commits before the route writes its audit event.
- **Database lifecycle:** replace startup `create_all()` with versioned migrations; use numeric money or integer francs with an explicit rounding rule; strengthen foreign-key/null/status/uniqueness constraints. Test a fresh PostgreSQL seed: the legacy seed inserts mutually referencing meter/customer rows differently from the safer demo generator.
- **Health:** `/health` returns HTTP success and `status="ok"` even when the database check fails. Separate liveness from readiness and always close failed database sessions.
- **Async behavior:** several `async` routes run synchronous ORM queries/password hashing/SMS directly. Move blocking work to appropriate sync handlers, thread workers, or background jobs, and set an inference concurrency budget before increasing workers.
- **Operational limits:** in-memory rate limits and lockouts are process-local and reset on restart. Verify the trusted proxy boundary; do not assume that any caller-supplied forwarded header is trustworthy. Bound request bodies at the server/proxy as well as checking declared length.
- **Frontend state:** `useRequest` has no latest-request guard; an older response can overwrite a later load. Some bill/payment effects omit customer ID dependencies. Include these race/account-switch cases in tests.
- **OTP lifecycle:** verification selects the latest unused code; older unexpired codes are not invalidated on resend. After using the newest, an older unused code can become eligible again. Invalidate prior challenges and atomically consume the current challenge.
- **Language:** both JSON catalogs have 362 keys and zero TODO values, but the three review CSVs contain no filled correction cells. This does not prove whether a human reviewed or approved the translations. Record reviewer/date/status; align SMS language with the household preference. Some misread messages incorrectly describe every digit-shift anomaly as a lower reading.
- **Documentation:** archive or update the parent `PROJECT_STATUS_FOR_CLAUDE.md`, old paths, GitHub placeholder, and historical statements. README says Node 18+, while locked tooling includes packages requiring newer Node. Declare a supported Node version and use it in CI.
- **Testing:** add a CI workflow; PostgreSQL integration checks; and a small browser suite for staff-only debt totals, close-only flags, duplicate submission, two reviewers, account switching, and the full reading-to-bill flow. The existing mocked frontend tests cannot catch mismatched auth headers across services.

## Recommended order

1. Close the USSD bypass and reject malformed numeric input.
2. Make submission/review writes atomic and idempotent; define billing periods and money rounding.
3. Fix staff bill authentication, unavailable-total handling, close-only flags, and household waiting status.
4. Bind drafts to accounts and retain photo/model evidence for reviewers.
5. Clearly label payment simulation, then build sandbox payment and notification reconciliation.
6. Add migrations, PostgreSQL integration tests, CI, session revocation, and readiness checks.
7. Conduct a consented field pilot with actual meter IDs, reviewed labels and translations; measure correction rates, reviewer workload, time to resolution, latency, data usage, and bill-impact errors.

For a capstone demonstration, simulated payments and synthetic histories can be acceptable when plainly labeled. Claims of autonomous accurate billing or production Mobile Money integration are not supported by the current implementation.

## Validation

Four frontend files changed independently while this review was running: `Screen.tsx`, `Screen.module.css`, `SignIn.tsx`, and `SignIn.module.css`. I inspected the late diff: it adds a narrow desktop sign-in layout and separate desktop submit buttons. Those edits were left intact and were not made by this review. The earlier build/test results below do not validate those subsequent edits; in particular, recheck sign-in tests and responsive button visibility.

| Check | Result |
|---|---|
| Frontend TypeScript | Passed (`npm run typecheck`) |
| Frontend production build | Passed (`npm run build`); separate staff bundle emitted |
| Frontend tests | Initial run: 127 tests in 19 files passed, but overall exit was failure because the camera-test thread worker timed out. Targeted retry with `--pool=forks`: 12 camera tests passed. Thus all 20 files and 139 tests passed across the two runs; there was no single clean full-suite run. |
| Full backend suite | Did not complete: API tests stalled in this environment. Interrupted; do not interpret progress dots as a completed pass. A SQLite-configured retry excluding real-model smoke tests also stalled. |
| Selected backend unit tests | **62 passed**, with one Pydantic deprecation warning: digit conversion, anomaly features/rules, password/token primitives, phone normalization, fake-model vision pipeline and guidance configuration. API/real-model/database integration were not covered by this selected run. |
| Catalog inventory | English: 362 keys; Kinyarwanda: 362 keys; zero TODO values in either. This does not validate translation quality. |
| Review inventory | 376 original tracked files individually listed, including 115 screenshots and 11 binary fonts. Only two screenshots were visually inspected. |

Direct isolated Python checks reproduced the following, using an in-memory database with SMS disabled:

- Calling the USSD handler without an authentication argument created a bill. This corroborates the unprotected route signature; it was a direct handler check, not an external HTTP exploit test.
- Submitting the identical cumulative reading again created a second bill for **RWF 1,000**, representing zero water plus another service charge.
- A staff token issued before a password change still passed `require_staff` afterwards.
- Accepting a flag attached to an already-confirmed reading raised the documented **409** error.
- Request schemas accepted `confirmed_reading="nan"` and infinite calculator consumption. These are validation-boundary checks, not claims that a particular database persists both values successfully.

The direct probes exercised local services only. No real payment was attempted, the notebook was not retrained, and official tariffs, live provider credentials, field accuracy, full browser accessibility, and deployed behavior were not independently verified.
