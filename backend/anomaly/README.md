# Stage 3 — Anomaly detection (Isolation Forest)

Stage 3 checks every new meter reading against **that household's own past readings** and flags
readings that look wrong (a CRNN misread) or worrying (a leak, a stuck meter). Stage 1 (MobileNetV2
quality gate) and Stage 2 (CRNN digit reader) run before it.

> **The bundled numbers come from DEMO data.** Before reporting any result, retrain and re-evaluate
> on real WASAC reading histories (see *Train* and *Evaluate* below).

In this backend a "household" is a **meter**: `household_id` is the `meter_id` that readings are
stored under.

## How a reading flows

```
CRNN digits "00565846"
   │  readings.py   8 wheels: first 5 = m3, last 3 = litres → 565.846 m3
   │                wrong length / non-digits → needs_retake (never guessed)
   ▼
features.py   compare with this household's previous readings (per day)
   ▼
rules.py      deterministic checks, always first
   ▼
model.py      one IsolationForest for all households (skipped during cold start)
   ▼
rules.py      name the model's anomaly (SPIKE / SUSTAINED_HIGH / MISREAD_SUSPECTED / UNUSUAL)
   ▼
service.py    AnomalyResult + row in anomaly_flags → notifications.py
```

## Features

All features are relative to the household's own history, so one shared model can judge a
household that uses 0.3 m3/day and one that uses 1.5 m3/day by the same standard. Households do not
submit on fixed dates, so everything is per day.

| Feature | Meaning |
|---|---|
| `days_since_last` | Days since the previous reading (minimum 1) |
| `consumption_m3` | New reading − previous reading |
| `daily_consumption` | `consumption_m3 / days_since_last` |
| `ratio_to_median` | Daily use ÷ median daily use of past periods |
| `robust_z` | (daily − median) ÷ (1.4826 × MAD), with a floor so MAD = 0 cannot divide by zero |
| `ratio_to_recent` | Daily use ÷ mean of the last 3 periods |
| `n_history` | Number of previous periods |

Ratios add 0.01 m3/day to both sides so a household that normally uses almost nothing does not
produce infinite ratios. The model sees three columns: `log(ratio_to_median)`,
`sign·log1p(|robust_z|)` and `log(ratio_to_recent)`. Logs tame the skew of ratios.

## Rules (run before the model, always)

| Condition | Result |
|---|---|
| First reading ever | `BASELINE`, never an anomaly |
| Reading lower than the previous one | `MISREAD_SUSPECTED`, retake photo (meters cannot run backwards) |
| Daily use above `ANOMALY_MAX_DAILY_M3` (default 5) | `SPIKE` |
| Zero consumption for `ANOMALY_STUCK_DAYS` or more (default 30, may span several readings) | `METER_STUCK` |
| Fewer than `ANOMALY_MIN_HISTORY_PERIODS` previous periods (default 3) | Cold start: rules only, no model |

## Model

One scikit-learn `IsolationForest` (`contamination=0.05`, `random_state=42`, 200 trees) is trained on
the feature rows of **all** households' historical periods. One model per household would not work
because a single household has too few readings. Periods that a rule already catches are left out
of training. The anomaly score is `-score_samples`, in (0, 1]; higher means more unusual.

If no trained model file exists, the service runs **rules only** and `/health` reports
`rules_only_model_not_trained`. The model is loaded once per process, so restart the API after
retraining.

When the model flags a period and no rule fired, it is named in this order:

1. Ratio to median within ×0.7–1.4 of **10×** or **100×** → `MISREAD_SUSPECTED` (looks like a shifted digit)
2. Ratio to median ≥ 3 → `SPIKE` (possible leak or burst pipe)
3. The last 3 periods all ≥ 1.5× median → `SUSTAINED_HIGH` (possible hidden leak)
4. Otherwise → `UNUSUAL`

The digit-shift check comes first because 10× also exceeds the spike ratio. As a result, a real
leak of about 10× is reported as a likely misread. Both types are held for staff review (see below),
so a person decides either way.

## Anomaly types and notifications

| Type | Reading | Household | WASAC staff (`requires_staff_review`) |
|---|---|---|---|
| `MISREAD_SUSPECTED` | **held** (`pending_review`) | SMS: your reading is being checked | yes: accept or reject |
| `SPIKE` | **held** (`pending_review`) | SMS: unusually high use, check for leaks | yes: accept or reject |
| `SUSTAINED_HIGH` | confirmed and billed (`anomaly_flagged`) | SMS: higher than normal for several periods | yes (follow-up) |
| `METER_STUCK` | confirmed and billed (`anomaly_flagged`) | — | yes |
| `UNUSUAL` | confirmed and billed (`anomaly_flagged`) | — | yes |

Wrong-length or non-digit CRNN output (`POST /api/anomaly/score` only) returns `needs_retake: true`
and an SMS asking for a new photo. It is logged as a flag with no staff action, because there is no
reading to decide on.

Every flagged result is stored in `anomaly_flags` (`status` = `open` / `resolved`).

## Pending review

`readings.validation_status` takes one of four values:

| Value | Billed | Moves `meters.last_reading` | Used as history |
|---|---|---|---|
| `valid` | yes | yes | yes |
| `anomaly_flagged` | yes | yes | yes |
| `pending_review` | no | no | **no** |
| `rejected` | no | no | **no** |

- A `MISREAD_SUSPECTED` or `SPIKE` reading is saved as `pending_review`. It is not billed, and the
  meter's last confirmed reading (`meters.last_reading`) stays where it was. The next submission is
  therefore judged against the last *confirmed* reading, so a 10× misread cannot block the next
  correct reading.
- A reading **lower than the last confirmed reading is not rejected any more**. It is saved as
  `pending_review` with type `MISREAD_SUSPECTED`, and the household is told it is being checked.
  This also applies to meters that have a `last_reading` on file but no reading rows, for example
  imported meters.
- Staff close the flag with `PATCH /api/anomaly/flags/{id}/resolve`:
  - `{"outcome": "accept"}`: the reading becomes `valid` and the new last confirmed reading. A bill
    is created against the previous confirmed reading, and the household gets an SMS with the
    amount. Accepting a reading *lower* than the last confirmed one (for example a replaced meter)
    resets the baseline and bills 0 m³ for that period. Accept is refused (409) if a newer reading
    for the meter is already confirmed; reject the old one instead.
  - `{"outcome": "reject"}`: the reading becomes `rejected`. It is kept for audit but never billed
    or used, and the household gets an SMS asking them to resubmit.
  - A pending flag must have an outcome (422 without one). Flags on other readings close without an
    outcome, and sending one returns 409.

No table changed for this. `validation_status` was already a free-text column, and the outcome can
be read from the reading's status.

SMS is **log-only for now**. `notifications.send_sms` has a TODO for Africa's Talking, using the
`AT_USERNAME` and `AT_API_KEY` environment variables. No keys are stored in code.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/anomaly/score` | `{household_id, reading_digits, reading_date?}`. Scores raw CRNN digits and stores a flag if anomalous. Does not store a reading or a bill. |
| `GET` | `/api/anomaly/flags?household_id=&status=open\|resolved&requires_staff_review=` | List flags, newest first |
| `PATCH` | `/api/anomaly/flags/{id}/resolve` | Close a flag; body `{"outcome": "accept" \| "reject"}` for a pending reading |

`/confirm-reading` and `/submit-ussd` store the reading, score it, and then either confirm and bill it
or hold it as `pending_review`. A held reading returns `success: true`,
`validation_status: "pending_review"` and no bill. USSD replies "being checked by WASAC before
billing". Both responses include an `anomaly` object with `pending_review`.

## Configuration (environment variables)

`ANOMALY_READING_LENGTH` (8), `ANOMALY_DECIMAL_DIGITS` (3), `ANOMALY_MAX_DAILY_M3` (5),
`ANOMALY_STUCK_DAYS` (30), `ANOMALY_MIN_HISTORY_PERIODS` (3), `ANOMALY_CONTAMINATION` (0.05),
`ANOMALY_RANDOM_STATE` (42), `ANOMALY_N_ESTIMATORS` (200), `ANOMALY_SPIKE_RATIO` (3),
`ANOMALY_SUSTAINED_RATIO` (1.5), `ANOMALY_SUSTAINED_PERIODS` (3),
`ANOMALY_MISREAD_LOG10_TOLERANCE` (0.15), `ANOMALY_MODEL_PATH`
(default `backend/anomaly/artifacts/isolation_forest.joblib`, gitignored).

## Train

Run these from `backend/`:

```bash
python scripts/train_anomaly_model.py                 # real readings in DATABASE_URL
python scripts/train_anomaly_model.py --csv real.csv  # columns: household_id,reading_date,reading_m3
python scripts/train_anomaly_model.py --demo          # DEMO data, pipeline testing only
```

Database training skips `DEMO-` meters and the three synthetic app seed meters (`MTR001`–`MTR003`).

## Evaluate

```bash
python scripts/evaluate_anomaly_model.py --train-split 0.7          # train on 70% of households, test on the rest
python scripts/evaluate_anomaly_model.py --csv real.csv --train-split 0.7
python scripts/evaluate_anomaly_model.py --demo --train-split 0.7   # DEMO only, labelled as such
```

For every reading with enough history, the script scores the true reading (false-alarm check) and
then the same reading with one injected error: last digit wrong, one dropped digit, one extra digit,
one wrong digit elsewhere, and a 3–10× leak. It reports the detection rate per error type, the false
alarm rate, and the mean size of the errors it missed. The script **refuses** to run on data that
contains `DEMO-` households unless `--demo` is passed, and labels demo output as not a real result.
Without `--train-split` it uses the saved model, which is in-sample if that model was trained on the
same households.

What to expect: a dropped or extra digit is always caught by the length check. A wrong **last**
digit changes the reading by at most 9 litres, so it is rarely flagged; the error is too small to
matter for billing, and the report shows how large the missed errors were.

## Demo households

```bash
python scripts/demo/generate_demo_households.py            # writes scripts/demo/output/DEMO_households.csv
python scripts/demo/generate_demo_households.py --load-db  # also inserts DEMO- meters into the database
```

These are about 20 synthetic households, generated only so the pipeline can run before WASAC data
arrives. Every id starts with `DEMO-`. **Retrain on real WASAC data before reporting any results.**

## Tests

```bash
pip install -r requirements-dev.txt
pytest            # from backend/; uses in-memory SQLite, never touches Postgres or a real model file
```
