# Approved proposal and delivered prototype

Source: September 2026 proposal text supplied by the author on 6 November 2026. This maps the
proposal to repository evidence; it does not assert that deviations have supervisor approval.
The main objective was to design, implement and evaluate an AI-assisted meter submission prototype
with a small group in one Kigali sector. Technical functionality is demonstrated; improvement over
manual reading and real-user usability remain unmeasured.

## Objectives and milestones

| Proposal milestone | Planned dates | Delivered evidence | Difference / remaining evidence |
|---|---|---|---|
| Phase 1: literature, data collection, recruitment | 3–16 Sep 2026 | Model notebook and configuration; documented 652 Benax photographs, 536 labelled readable images and 98 unreadable images; proposal describes 13 field observations | No verified recruitment, consent records or pre-intervention surveys supplied. The 13 observations are not the planned pilot. Actual milestone completion dates must come from the author's records |
| Phase 2: backend and models | 17 Sep–7 Oct | `backend/app`, `backend/ml`, `notebooks`; three-model inference pipeline | Quality model is server-side and advisory. Additional institutional WASAC data and real consumption histories were not obtained |
| Phase 3: frontend | 8–28 Oct | Household and staff React pages; camera, confirmation, bills, messages, simulated payments | 56 Kinyarwanda placeholders still require human translation; live MTN settlement was never evaluated |
| Phase 4: anomaly detection and usability | 29 Oct–11 Nov | Rules, officer review and offline synthetic forest evaluation | Forest not deployed; first participant usability session not evidenced |
| Phase 5: pilot and final report | 12–28 Nov | Technical report and technical test evidence | As of 6 Nov these dates are future. No pilot, second session, SUS or interviews have been completed. Do not label this milestone completed |

The proposal also calls the evaluation a **three-month pilot**, but its last phase lasts about
17 days. Obtain an explicit revised evaluation schedule and scope decision; a short demonstration
cannot be described as the promised longitudinal pilot.

## Functional requirements

| ID | Proposal | Current status and evidence |
|---|---|---|
| FR1 | Photo and prediction in about 5 s | Implemented: `vision/pipeline.py`, camera screen. Historical warm-server times 1.3–3.7 s; cold starts can exceed a minute. Not an unconditional latency guarantee |
| FR2 | Real-time camera guidance | Implemented with server frame requests (`/guide-frame`); soft advice rather than an on-device rejection gate |
| FR3 | Confirm or correct reading | Implemented: counter, `/check-reading` and `/confirm-reading`; API and frontend tests |
| FR4 | Basic-phone USSD shortcode | Menu and callback implemented/tested; live shortcode not connected |
| FR5 | Reject lower readings | Deliberately changed to an officer hold. Meter replacement, errors and rollover need a human decision; first reading without a baseline is not billed |
| FR6 | Historical forest checks on every reading | Partial: deployed rules and historical comparisons; forest evaluated only on synthetic data. No validation on real customer histories |
| FR7 | Indicative domestic tariff bill | Implemented with versioned tariffs and VAT breakdown; effective date and service charge unconfirmed. Bills are prototype estimates, not official WASAC bills |
| FR8 | SMS receipt within 10 s | Sending logic and sandbox outbox exist; real delivery and timing not measured |
| FR9 | SMS review notification within 24 h | Notification logic exists; production delivery not demonstrated. In-app messages provide a separate channel |
| FR10 | GPS mismatch rejection | Deliberately changed to review. GPS is uncertain and spoofable, so it is supporting evidence rather than proof |
| FR11 | Officer submits for multiple accounts on a field round | Staff can manage and review multiple accounts; no dedicated staff camera/field-round submission screen. API capabilities alone do not complete this workflow |
| FR12 | MTN sandbox payment simulation | Simulation and staff-confirmed MoMo Pay exist; MTN API paths are mock-tested. No successful provider sandbox transaction evidenced |

Additional features include corrections with second-person approval, account credit, customer CSV
imports, next-bill estimates, possible-leak warnings, and sector prioritization. They do not replace
missing proposal commitments.

## Non-functional requirements

| ID | Proposal | Current evidence / gap |
|---|---|---|
| NFR1 | Prediction under 5 s on mobile internet | Historical warm inference measurements, not a representative field-network guarantee; cold-start limitation documented |
| NFR2 | On-device quality check under 200 ms | Not met: inference is server-side. Change justified by deployment simplicity and advisory behavior; approval still required |
| NFR3 | iOS Safari and Android Chrome | Three browser engines at simulated sizes, plus one manual phone test. No recorded representative Android field test; engine checks are not every actual device |
| NFR4 | No identifying information in any table | Not met by the application schema: customer names, phones and review GPS evidence are stored. Current accounts are synthetic. Research records need pseudonymous IDs and a separately controlled contact register, or an approved amended data plan |
| NFR5 | Full privacy-law compliance | Not established by code tests. Access checks and retention are controls, not a compliance certification. Resolve the proposed consent, hosting, access and deletion plan before real participants |
| NFR6 | 15 participants without degraded response time | Local endpoint load and PostgreSQL concurrency tests support particular behaviors; no full photo workflow load measurement for 15 real participants |
| NFR7 | 99% pilot uptime | No longitudinal uptime record. Free hosting sleeps; readiness endpoint exists, but monitoring must be configured and measured |

## Data handling differences needing a decision

The proposal says participant records use anonymous IDs, GPS is not retained, data lives only on ALU
Drive, and deletion occurs within three months after study completion. The current application uses
Neon/Render, stores account contact information and GPS evidence, and expires photos by age (90 days
by default). These are different purposes, storage locations and retention rules. The synthetic
demonstration must not be silently converted into a real participant deployment. Amend the data
management plan and obtain the relevant approval before real recruitment or importing customer data.

## What can be concluded

The artifact demonstrates a connected, traceable workflow and tested technical controls. It does
not establish improved reading accuracy versus independent manual readings, reduced staff workload,
SUS scores, adoption, real leak identification, delivered SMS timing or live payment settlement.
