# Open items: what still needs real-world validation or a policy decision

The code cannot settle these. Nothing here was guessed into the app as if it were confirmed.

## Needs WASAC or RURA

| Item | Today | Why it matters |
|---|---|---|
| Tariff rates and service charge | `v1-provisional` in `backend/app/services/tariffs.json`, from the project brief | Every bill depends on it. When confirmed, add a new version; never edit one that bills use |
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

- **Kinyarwanda.** All new strings are unreviewed drafts: `docs/i18n/kinyarwanda_review_reliability.csv`.
- **Double-payment refunds.** A second success becomes credit automatically and is listed for staff, who
  mark it reviewed. Whether a household gets its money back another way is WASAC's decision.
- **Second-person check on payment reconciliation.** One supervisor can reconcile, with evidence in the
  audit log. A second approver could be added if WASAC's controls require it.
