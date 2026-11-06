# Open items: what still needs real-world validation or a policy decision

The code cannot settle these. Nothing here was guessed into the app as if it were confirmed.

## Needs WASAC or RURA

| Item | Today | Why it matters |
|---|---|---|
| Tariff rates and service charge | `v2-wasac-residential` in `backend/app/services/tariffs.json`, from WASAC's published residential tariff, used from 3 November 2026. The service charge of 1,000 is kept from the project brief | The effective date and the service charge are not confirmed. When they are, add a new version; never edit one that bills use |
| VAT on the service charge | None: VAT is added on the water only | The published tariff gives VAT-inclusive water rates but says nothing about a service charge |
| Customer types | Everyone is billed as residential | WASAC publishes other rates for non-residential customers (877, 895 above 50 m³), public taps (323 flat) and industries (736 flat). These need a customer type on each household |
| Lower readings | Accepting a reading below the last one resets the meter's start and bills only the service charge | Whether WASAC charges for that period |
| Tier scaling for long periods | Tiers apply per bill, however long the period | A 60-day gap pushes use into higher tiers. Whether tiers scale with days is a tariff rule |
| Charge for a period with no known start | A baseline correction bills reading minus start; start equal to the reading bills nothing, not even the service charge | Follows the decision that a first reading creates no bill. WASAC may want the service charge |
| Rounding of bills | Bills keep 2 decimals; payments are whole francs, half up, so a bill can leave under one franc of credit | WASAC's own rounding rule is unknown |
| Refunds | No cash refunds: overpayments stay as credit | Credit on a closed account needs a process outside the app |

## Needs real consumption histories

All thresholds are provisional: see "Thresholds are provisional" in `backend/app/anomaly/README.md`.
Once WASAC data arrives, measure the share of readings held and how often officers accept them.

- **`ANOMALY_SPIKE_RATIO` (3x).** A ratio says nothing about size. A household using 0.05 m³/day is held
  at about 0.17 m³/day, 5 m³ a month, which is cheap. If the queue fills with these, a minimum extra
  volume could be added; none was added because that would be a new, unvalidated number.
- **`ANOMALY_MAX_DAILY_M3` (5).** Far above household use, but shared compounds or businesses may pass it.
- **`ANOMALY_EDIT_HOLD_M3` (1).** Depends on how often the reader is right on real photos. On the held-out
  set it read 55.7% of 79 photos exactly (95% CI 42–69%).
- **`ANOMALY_MIN_PERIOD_DAYS` (7), `ANOMALY_STUCK_DAYS` (30), `ANOMALY_MIN_HISTORY_PERIODS` (3).** Chosen by reasoning only.
- **Leak alert, `ANOMALY_LEAK_RATIO` (1.5x) and `ANOMALY_LEAK_MIN_EXTRA_M3` (3).** Only tells the household; it never
  holds a reading. Chosen by reasoning only: measure how often households who get it find a real leak.
- **Next-bill estimate.** Usual daily use times a usual period, on today's tariff. It is shown as an estimate, not a
  bill, and a number typed for it is never stored. How close it comes to the real bill is unmeasured.
- **Isolation Forest.** Not deployed, and only ever trained on synthetic households. Its results must not be
  reported as real-world performance.

## Needs MTN

- **404 on the status check.** MTN's documentation says the reference id is not known and points to the
  original request, but does not cover a 404 after a 202. So a 404 never closes an attempt: a supervisor
  does, from MTN's records. Ask MTN what a 404 after a 202 means. No sandbox keys were available, so this
  has only been tested with mocks.
- **How long a prompt can stay live.** Staff closures and old local failures are asked about again for
  24 hours (`RECHECK_WINDOW`). Confirm that MTN expires prompts well within that.
- **Live currency and rounding.** The sandbox uses EUR; live uses RWF.

## Needs a person

- **Kinyarwanda.** 56 placeholders are collected in `docs/i18n/kinyarwanda_review_final_review.csv`.
  A human reviewer must fill the correction column. Other translations also need human review.
- **Double-payment refunds.** A second success becomes credit automatically and is listed for staff, who
  mark it reviewed. Whether a household gets its money back another way is WASAC's decision.
- **Second-person check on payment reconciliation.** One supervisor can reconcile, with evidence in the
  audit log. A second approver could be added if WASAC's controls require it.

## Needs the supervisor and research approvals

- **Scope changes.** See `docs/SCOPE_ALIGNMENT.md` for the supplied September proposal's FR1–FR12,
  NFR1–NFR7 and five phases. The implementation choices are documented, not retrospectively approved.
- **Pilot duration.** The proposal promises three months but schedules the final evaluation for
  12–28 November. Confirm a feasible revised plan; no pilot or SUS result has been collected.
- **Privacy design.** The proposal promises anonymous records, no retained GPS and ALU Drive-only
  storage. The app stores contact information and GPS review evidence on Neon/Render. Current
  households are synthetic. Resolve consent, purpose, hosting, access and retention before real data.
- **Officer field-entry mode.** Staff review and manage many accounts, but there is no dedicated
  field-round camera screen corresponding to FR11. Agree whether this remains a deliverable.
- **Institutional data and model validation.** Obtain authorized local data and verified outcomes
  before retraining or claiming improvements in accuracy, workload, usability or physical leak detection.
- **Service readiness.** Configure external monitoring and a scheduler, verify a backup of the actual
  deployment, and obtain an independent security review. A local synthetic restore drill is not a
  recovery test of Neon or a compliance certification.
