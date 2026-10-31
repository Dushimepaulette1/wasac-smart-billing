# Algorithms and problem solving

| Problem | Solution | Where |
|---|---|---|
| Read 8 rolling wheels from a photo | YOLO finds the window; ResNet18 + BiGRU; CTC greedy decoding merges repeats and drops blanks, with a confidence per digit | `backend/app/vision/pipeline.py`, `backend/ml/wasac_models.py`, `backend/app/vision/onnx_models.py` |
| Is the photo usable? | MobileNetV2 and calibrated thresholds give advice but never block | `backend/app/vision/guidance.py`, `docs/calibration/guidance_calibration.md` |
| Is this reading believable? | Rules first (lower reading, over 5 m³ a day, 3x usual, stuck meter), then Isolation Forest when a trained model exists | `backend/app/anomaly/rules.py`, `scoring.py`, `features.py` |
| Replaced meters confuse history | `since_last_reset` starts history after the last drop | `backend/app/anomaly/scoring.py` |
| Did the household lower a good AI read? | Compares digits only when the read is complete and reliable | `backend/app/anomaly/edits.py` |
| Was the photo taken at the meter? | Distance from the meter's location against GPS accuracy | `backend/app/anomaly/location.py` |
| Register wraps at 99,999 | Use across the wrap, always confirmed by an officer | `backend/app/anomaly/readings.py` |
| Tiered tariff | Walks the tiers of the bill's own tariff version, rounded to avoid float noise | `backend/app/services/billing.py` |
| Spend credit fairly | Oldest bill first, one household at a time, skipping bills with money in flight | `backend/app/services/balance.py` |
| Two requests at once | Row locks, partial unique indexes, idempotency keys | `backend/app/services/payments.py`, `backend/app/db/init_db.py` |
| Bill correction | Recalculates this bill and the next with their own tariffs, without changing originals | `backend/app/services/bill_corrections.py` |
| Measure anomaly detection with no real histories | Seeded simulation with known injected faults, then precision, recall and F1 with customer-level bootstrap intervals | `backend/simulation/`, `backend/scripts/run_simulation.py` |

## Offline simulation of anomaly detection

**All results here are synthetic. They are not evidence of real WASAC performance.** The simulation
is separate from the app: no route, table or deployed model uses it, and production stays rules only.

To reproduce it, run this from `backend/` (about 40 seconds). The results go to the gitignored folder
`backend/simulation/output/`: `metrics.json`, `confusion_matrices.png` and the CSV files.

```
python scripts/run_simulation.py --seed 42
```

### Method

| Step | What happens | Where |
|---|---|---|
| Data | 500 customers over 12 months: 90% domestic (log-normal, 5–25 m³), 10% commercial (log-normal, 50–200 m³). The ranges are the 5th to 95th percentiles. | `simulation/config.py`, `generate.py` |
| Faults | 5% of Active months: leaks at 3–5x use for 3–6 months, bypasses at 0–5% of use for 2–6 months. A fault starts only after 3 Active months. | `simulation/generate.py` |
| Billing | Active, Disconnected, Reconnection. One unpaid bill closes the water; paying the arrears adds a 20,000 RWF penalty. These rules are assumptions, not confirmed WASAC rules. | `simulation/ledger.py` |
| Features | The app's three model features plus `volumetric_deviation`, measured against the mean of the first 3 Active months, then frozen so a long leak cannot raise its own baseline. | `simulation/detect.py` |
| Training | Isolation Forest with the app's `AnomalyConfig`, on 350 customers. The other 150 are held out. | `simulation/detect.py` |
| Evaluation | Rules only, forest only, and either one flagging a month. 2,000 bootstrap resamples of whole customers give the 95% intervals. | `simulation/evaluate.py` |

Labels cannot reach the detector: it receives six label-free fields, and a test corrupts every label
and confirms the detections do not change. `consecutive_unpaid_months` was dropped, because one
unpaid bill disconnects a customer at once, so it is always 0 in the months being scored.

### Results, seed 42

1,174 test months from 150 held-out customers, of which 88 were fault months.

| Setup | Precision (95% CI) | Recall (95% CI) | F1 (95% CI) | False alarms |
|---|---|---|---|---|
| Rules only (live today) | 0.548 (0.325–0.775) | 0.455 (0.271–0.640) | 0.497 (0.311–0.657) | 33 |
| Forest only | 0.854 (0.755–0.926) | 0.932 (0.857–0.988) | 0.891 (0.820–0.945) | 14 |
| Rules + Forest | 0.689 (0.526–0.843) | 0.932 (0.857–0.988) | 0.792 (0.670–0.891) | 37 |

- **Forest compared with rules:** F1 is 0.394 higher (paired 95% CI 0.251–0.566), so the interval excludes zero.
- **Leaks:** rules caught 40 of 52 fault months; the forest caught 50 of 52.
- **Bypasses:** rules caught 0 of 36, a real blind spot, because the stuck-meter rule needs a true zero. The forest caught 32 of 36.
- **Commercial false alarms:** rules flagged 28.8% of normal commercial months, because the limit of 5 m³ a day was set for households. The forest flagged 9.9%. Domestic rates were 0.1% and 0.3%.
- **Adding the rules to the forest:** this caught no extra fault months at seed 42 and added 23 false alarms.

### Checks on the headline

| Check | Rules | Forest | Rules + Forest |
|---|---|---|---|
| Mean F1 over 20 other seeds (lowest–highest) | 0.432 (0.331–0.542) | 0.884 (0.829–0.932) | 0.809 (0.728–0.896) |
| F1 with subtle faults, seed 42 (95% CI) | 0.049 (0.000–0.158) | 0.667 (0.518–0.775) | 0.600 (0.446–0.737) |

Subtle faults are leaks at 1.5–2.5x use and bypasses at 40–60% of use. Forest recall drops from 0.932
to 0.670, and bypass recall to 16 of 36.

### Limits

- The faults were designed by the author, so they fit these features more closely than real faults may.
- The forest's `contamination` of 0.05 equals the injected fault share. Real fault rates are unknown, so this flatters the forest.
- Only 9 commercial fault months are in the seed 42 test set, so commercial results are weak.
- These results do not justify deploying the forest. That needs real WASAC histories.
