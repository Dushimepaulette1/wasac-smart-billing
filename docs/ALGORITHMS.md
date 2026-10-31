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
