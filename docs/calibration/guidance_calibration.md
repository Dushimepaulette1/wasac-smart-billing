# Photo guidance calibration

This document shows how the photo-guidance thresholds in `backend/vision/guidance_config.json` were
chosen. Guidance codes tell a household how to improve a meter photo. None of them blocks a
submission; `NO_METER` only means that no reading is suggested.

> **Note.** The Benax YOLO model may have been trained on some of these photos, so the NO_METER
> results may be slightly optimistic; re-run on new WASAC photos when available.
>
> In the same way, the readable photos are the meter reader's training labels, and the unreadable
> photos were negative examples for the quality gate. The HARD_TO_READ and CHECK_NUMBERS rates are
> therefore also likely optimistic. The **held-out** table below uses only photos that were never
> used in training. On them, HARD_TO_READ still separates the groups (11% vs 60%), but CHECK_NUMBERS
> barely does (15% vs 20%). The thresholds were left unchanged.

## Method

- **Meter photos:** 652 full photos of WASAC meters in Kigali, grouped with the project's label
  files:
  - **readable** (in the reader's training labels): 536;
  - **unreadable** (marked unreadable): 98;
  - **unlabelled**: 18, of which 1 could not be decoded because it is too large (rejected exactly as
    the API rejects it). Unlabelled photos were used only for the NO_METER check.
- **Non-meter images:**
  - **patches**: 1,132 background patches cut from meter photos away from the detected number
    window (each at least 30% of the photo's width and height), showing pipes, soil, walls and meter
    boxes;
  - **coco**: 50 everyday images from the COCO 2017 validation set.
- **Each image was measured twice:**
  - as `/submit-photo` sees it: long side 1,600 px, YOLO at 640, quality gate and reader on the crop;
  - as `/guide-frame` sees it: a 640 px JPEG, YOLO at 640, 416 and 320.
- **Rules for choosing thresholds:**
  - NO_METER must leave at least 97% of real meter photos (readable and unreadable together)
    unflagged.
  - Every other check must fire clearly more often on unreadable than on readable photos (at least
    10 percentage points) and on no more than about 10% of readable photos.
- **Timing:** CPU only (8-core laptop, WSL, PyTorch using 4 threads), models warm.

## Chosen thresholds

| Check | Setting | Value | Status | Readable / unreadable | How it was chosen |
|---|---|---|---|---|---|
| NO_METER | window confidence | 0.35 | calibrated | 1.1% / 11.2% (all meters 2.7%) | Highest value keeping ≥ 97% of real meters. Non-meters passing as a meter: patches 0.5%, COCO 0% (4% in live frames). |
| guide frame size | YOLO input | 640 px | calibrated | – | 416 and 320 wrongly flag 5.4% and 11.5% of meters (640: 2.4%), for only 118 and 189 ms less per frame |
| TOO_FAR | window narrower than | 20% of width | provisional | 6.7% / 8.2% | No separation; the labels do not capture distance. Soft hint. |
| CUT_OFF | window within | 1% of an edge | provisional | 1.1% / 0.0% | Too rare to validate. Soft hint. |
| TOO_DARK | mean brightness below | 60 | provisional | 0.6% / 0.0% | Almost no dark photos in the set. Soft hint. |
| GLARE | near-white pixels over | 10% | provisional | 4.7% / 7.1% | No value separates the groups. Raised from 5% to halve how often good photos get it; use a soft message. |
| BLURRY | Laplacian variance below | off | turned off | – | At every useful value it fired more on readable photos (e.g. 39% vs 26%): dirty glass adds texture. |
| HARD_TO_READ | quality-gate P(unreadable) at least | 0.50 | calibrated | 8.4% / 83.7% | The model's own 0.43 gives 12.5% / 88.8%, above the 10% limit |
| CHECK_NUMBERS | lowest digit confidence below | 0.50 | calibrated | 9.7% / 32.7% | 0.6 gives 26% / 50% |

The quality gate fires far more often on unreadable photos than on readable ones, which confirms its
class index (`positive_class_index: 1`).

The tables below are the measured rates with the chosen thresholds. In the NO_METER table, the
non-meter columns show the share **wrongly accepted as a meter**. Everywhere else, a cell is the
share of images in that group for which the code fired. One image can get several codes.

## Held-out photos (never used in training)

HARD_TO_READ and CHECK_NUMBERS on the test split of the training run only: photos that neither the reader nor the quality gate saw during training. **This is a small sample** (see the 95% confidence intervals), so these numbers are indicative; the thresholds were not changed because of them.

| Code | Threshold | readable (held-out) | unreadable (held-out) |
|---|---|---|---|
| HARD_TO_READ | 0.5 | 9/79 = 11.4% (95% CI 6–20%) | 9/15 = 60.0% (95% CI 36–80%) |
| CHECK_NUMBERS | 0.5 | 12/79 = 15.2% (95% CI 9–25%) | 3/15 = 20.0% (95% CI 7–45%) |

## Data

| Group | Images |
|---|---|
| readable | 536 |
| unreadable | 98 |
| unlabelled | 17 |
| patches | 1132 |
| coco | 50 |

## NO_METER

Share of real meter photos wrongly flagged NO_METER, and share of non-meter images that wrongly pass as a meter:

| Setting | readable | unreadable | all meters | patches passed as meter | coco passed as meter |
|---|---|---|---|---|---|
| /submit-photo (YOLO 640) | 1.1% | 11.2% | 2.7% | 0.5% | 0.0% |
| /guide-frame at 640 | 1.1% | 9.2% | 2.4% | 0.3% | 4.0% |
| /guide-frame at 416 | 4.5% | 10.2% | 5.4% | 0.4% | 2.0% |
| /guide-frame at 320 | 11.0% | 14.3% | 11.5% | 0.1% | 4.0% |

## Code rates: /submit-photo (YOLO 640, quality gate and reader on the crop)

| Code | readable | unreadable | unlabelled | patches | coco |
|---|---|---|---|---|---|
| NO_METER | 1.1% | 11.2% | 64.7% | 99.5% | 100.0% |
| TOO_FAR | 6.7% | 8.2% | 17.6% | 0.0% | 0.0% |
| CUT_OFF | 1.1% | 0.0% | 0.0% | 0.2% | 0.0% |
| TOO_DARK | 0.6% | 0.0% | 11.8% | 30.8% | 4.0% |
| GLARE | 4.7% | 7.1% | 11.8% | 1.9% | 12.0% |
| BLURRY | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| HARD_TO_READ | 8.4% | 83.7% | 52.9% | 10.2% | 14.0% |
| CHECK_NUMBERS | 9.7% | 32.7% | 5.9% | 0.3% | 0.0% |
| OK | 72.6% | 8.2% | 11.8% | 0.0% | 0.0% |

## Code rates: /guide-frame, YOLO at 640

| Code | readable | unreadable | unlabelled | patches | coco |
|---|---|---|---|---|---|
| NO_METER | 1.1% | 9.2% | 64.7% | 99.7% | 96.0% |
| TOO_FAR | 6.7% | 9.2% | 17.6% | 0.0% | 0.0% |
| CUT_OFF | 0.6% | 0.0% | 0.0% | 0.3% | 0.0% |
| TOO_DARK | 0.7% | 0.0% | 11.8% | 30.4% | 4.0% |
| GLARE | 4.7% | 8.2% | 11.8% | 1.9% | 12.0% |
| BLURRY | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| OK | 86.8% | 74.5% | 17.6% | 0.0% | 4.0% |

## Code rates: /guide-frame, YOLO at 416

| Code | readable | unreadable | unlabelled | patches | coco |
|---|---|---|---|---|---|
| NO_METER | 4.5% | 10.2% | 58.8% | 99.6% | 98.0% |
| TOO_FAR | 4.7% | 3.1% | 5.9% | 0.2% | 2.0% |
| CUT_OFF | 0.7% | 1.0% | 0.0% | 0.3% | 2.0% |
| TOO_DARK | 1.7% | 1.0% | 11.8% | 30.6% | 4.0% |
| GLARE | 5.2% | 8.2% | 11.8% | 2.0% | 14.0% |
| BLURRY | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| OK | 84.9% | 78.6% | 29.4% | 0.1% | 0.0% |

## Code rates: /guide-frame, YOLO at 320

| Code | readable | unreadable | unlabelled | patches | coco |
|---|---|---|---|---|---|
| NO_METER | 11.0% | 14.3% | 47.1% | 99.9% | 96.0% |
| TOO_FAR | 1.1% | 6.1% | 0.0% | 0.0% | 0.0% |
| CUT_OFF | 1.7% | 1.0% | 0.0% | 0.1% | 2.0% |
| TOO_DARK | 3.5% | 3.1% | 11.8% | 30.7% | 4.0% |
| GLARE | 4.7% | 7.1% | 11.8% | 2.0% | 8.0% |
| BLURRY | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| OK | 81.2% | 74.5% | 41.2% | 0.0% | 2.0% |

## Timing (CPU, warm)

| Call | Median | 90th percentile |
|---|---|---|
| /submit-photo (incl. quality gate and reader) | 636 ms | 2095 ms |
| /guide-frame, YOLO at 640 | 405 ms | 1298 ms |
| /guide-frame, YOLO at 416 | 287 ms | 1112 ms |
| /guide-frame, YOLO at 320 | 216 ms | 853 ms |
