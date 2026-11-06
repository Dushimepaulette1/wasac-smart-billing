# Pilot evaluation protocol — proposed, not conducted

Use with supervisor/institutional approval and participant consent. Do not upload real participant
records until the data-handling differences in `docs/SCOPE_ALIGNMENT.md` are resolved. The September
proposal specifies 10–15 adult households and 2–3 field officers in one approved sector. Confirm the
duration: the stated three months does not fit the final phase's November dates.

## Comparison and records

Assign research IDs; keep the contact/consent register separately with restricted access. Have an
independent reader establish the true meter value at each observed session. Record the unassisted
manual reading, raw AI suggestion, confirmed reading, elapsed time, any assistance, and review
outcome separately. Do not treat household edits as verified labels. Use only approved storage and
retention; photographs and location can identify a household even when its name is removed.

## Eight household tasks

1. Sign in and identify the correct meter.
2. Find the previous reading and submission eligibility date.
3. Capture a meter photograph using guidance.
4. Verify and, where needed, correct the suggested digits.
5. Explain a held-reading message and submit for review.
6. Find the bill and explain consumption, VAT and the service charge.
7. Complete a simulated payment and recognize pending versus confirmed status.
8. Find history/messages and explain a next-bill estimate or possible-leak warning.

For each task record success without help, success with help, failure, duration, errors and a short
observation. Report the denominator and whether assistance counts as success; do not mix the two.
For staff observe reviewing evidence, accepting/rejecting a synthetic reading with a reason, finding
a household from Sectors, and making a correction that needs a second approver.

## Analysis

| Measure | Numerator / method | Important limit |
|---|---|---|
| Exact reading accuracy | Entire predicted sequence correct / all evaluated photos | Separate raw AI from human-confirmed results; identify meter-level split |
| Integer accuracy | Correct whole-m³ portion / evaluated photos | A correct integer can still have wrong litres |
| Digit error | Edit distance and per-position correctness with stated alignment rule | Do not rename "within one digit" as digit-level accuracy |
| Quality false warning | Readable images warned / readable images | Model is advisory, so this is not actual submission rejection |
| Anomaly precision | Independently verified unusual events / reviewed flags | An accepted reading is not automatically proof of a physical leak |
| Review workload | Held submissions / all submissions; officer time per case | Record reasons and false alarms |
| Task completion | Tasks completed / attempted; separately unassisted | Small convenience sample cannot represent all Kigali households |
| SUS | Supervisor-approved standard instrument and scoring | No invented scores; record response count and missing responses |
| Awareness | Matched pre/post answers on the same five-point questions | Describe exploratory changes, not causal proof |
| Latency | End-to-end upload-to-result; median and p95, cold/warm separated | Include device, network, photo size and failures |

Retain the original evaluation set. New labelled local photos should first support training and
validation; collect a separate, previously unseen test set from different meters for the next final
evaluation. Measure errors by lighting, meter type, orientation and wheel transitions. Obtain
permission for reuse and verify correction labels before training.

## Device and connectivity record

Use at least a representative lower-cost Android phone and an iPhone if available. Record model,
OS, browser, connection, camera/location permissions, language and screen size. Test denied camera
permission, denied GPS, dropped upload, retry, and account isolation. Keep device evidence separate
from browser-emulated sizes and simulated CPU/network throttling.

Report unsuccessful sessions and missing data. The proposed protocol is preparation, not evidence
that recruitment, consent, a pilot or any stated target has been achieved.
