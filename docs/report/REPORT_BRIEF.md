# Capstone report brief: Mubazi (WASAC smart water billing)

This brief gives a writing assistant every fact about the project needed to help draft the final
capstone report. Everything below comes from the project's code, notebook, documents and test
runs. Items marked **[FILL IN]** are things only the student has (supervisor feedback, Kaggle
numbers, literature details); they must not be invented.

## 0. Rules for the assistant

1. **Do not invent numbers, results, quotes or references.** Use only the figures in this brief.
   If a figure is missing, write **[FILL IN]**.
2. **References:** only cite sources the student can open and check. Section 15 lists real,
   well-known works to look up; confirm each one (authors, year, venue) before citing. Use **APA 7**
   (or the citation style in the ALU template if it says otherwise).
3. **Plagiarism:** help the student write in their own words. No copied text from papers or
   websites; paraphrase and cite. The student is responsible for the final wording.
4. **Be honest about limits.** The project's results are modest and the sample is small. The report
   is stronger when it says so clearly (see Sections 10 and 11).
5. Follow the **ALU report template** for headings and order. Map content to it using Section 14.

---

## 1. Project identity

| Item | Value |
|---|---|
| Product name | **Mubazi** (Kinyarwanda for the water meter) |
| Full title (suggested) | *Mubazi: an AI-assisted meter reading and billing platform for WASAC water customers in Rwanda* |
| Author | Dushime Paulette |
| Programme | BSc Software Engineering (Machine Learning), African Leadership University (ALU) |
| Supervisor | Samiratu Ntoshi |
| Partner / context | WASAC (Water and Sanitation Corporation, Rwanda's water utility) as the target user; no formal partnership. **[FILL IN if there was any contact with WASAC]** |
| Live app | https://wasac-smart-billing-qt9t.vercel.app (staff area at `/staff`) |
| Live API | https://wasac-api.onrender.com (API docs at `/docs`) |
| Source code | https://github.com/Dushimepaulette1/wasac-smart-billing |
| Project period | 1 August 2026 to 27 October 2026 (172 commits) |

## 2. Problem and context

- WASAC households have mechanical water meters with 8 rolling wheels: 5 black wheels for cubic
  metres and 3 red wheels for litres (for example `00565846` = 565.846 m³).
- Meters are read by hand. Manual reading is slow and costly, and it produces estimated bills,
  misread digits and disputes. Hidden leaks are found late because consumption is checked rarely.
- Many households have only a basic phone or patchy mobile data.
- **[FILL IN with sources]** National context: urbanisation of Kigali, non-revenue water,
  WASAC billing complaints, mobile money adoption (MTN MoMo), smartphone vs feature-phone
  ownership in Rwanda. Each claim needs a real citation (WASAC/RURA reports, NISR statistics,
  GSMA Mobile Economy reports). Do not state national figures without a source.

## 3. Objectives (as built)

1. Let a household read its own meter with a phone photo, and have the system read the digits.
2. Warn the household when a photo is likely unreadable, without ever blocking them.
3. Check every reading against the household's own history and hold suspicious readings for a
   WASAC officer instead of billing them.
4. Bill accepted readings on the tiered tariff, and let the household pay with mobile money.
5. Serve households without smartphones (USSD) and in Kinyarwanda first.
6. Give WASAC staff a dashboard to review held readings quickly and fairly, with evidence.

## 4. Research questions (suggested wording)

1. How accurately can a deep-learning pipeline read Kigali water meters from household phone
   photos, given a small local dataset?
2. Does pretraining on a foreign meter dataset (Yandex, Russia) improve reading accuracy on Kigali
   meters, and how large is the domain gap?
3. Can a lightweight image classifier flag unreadable photos well enough to guide households?
4. Can per-household anomaly detection (Isolation Forest plus rules) catch misreads and leaks
   before they become bills?
5. Can such a system run end to end on free cloud infrastructure for low-bandwidth users?

---

## 5. Methodology: the machine-learning pipeline

### 5.1 Data

| Source | Description | Size | Use |
|---|---|---|---|
| Kigali (Benax) photos | Real photos of WASAC meters in Kigali, shared for academic use by the developer of a public Rwandan YOLOv8 meter model ("Benax") | 652 photos | Fine-tuning and testing |
| Verified labels | Every crop checked by the student by eye: confirmed, corrected, or marked unreadable | 536 readable readings + 98 unreadable | Ground truth |
| Yandex Toloka water meters | Public dataset of meter photos from Russia, licence CC BY-NC-ND 4.0 | 1,244 photos (1,119 used for pretraining training) | Pretraining |

Label quality work (a real finding worth reporting):
- Many Kigali labels had **lost their leading zeros** (a spreadsheet saved `00565846` as `565846`).
  Zeros were restored with a tested method that only ever adds zeros and never touches labels the
  student typed. **Reading accuracy ignores leading zeros**, because they never change a bill.
- Yandex labels stored as decimals (`21.86`) lost digits and gained floating-point noise; this
  caused an early training collapse (the CTC "blank trap"). Labels were rebuilt from the file
  names as full 8-wheel strings. An overfit test on 32 images proved the code was correct and the
  labels were the problem.
- Some Yandex crops were upside down; the first-round model was used to pick the right orientation
  per crop (lowest CTC loss), with an honesty note that this slightly inflates the Yandex
  validation score only.

### 5.2 Splitting (no leakage)

- The same meters were photographed many times (up to 14). Photos were grouped into meters with a
  union-find on matching readings; the split is **by meter**, 70 / 15 / 15 (train / validation /
  test), with automatic checks that no meter is shared.
- Training keeps at most 4 photos per meter. The test set (**79 photos of 34 meters**) was used
  **once**, after the model was chosen.
- Yandex: 90 / 10 split (pretraining only). Unreadable crops: 70 / 15 / 15 at random (they cannot be
  grouped by meter, a stated limitation).

### 5.3 Models

| Stage | Job | Model |
|---|---|---|
| 0 | Find the number window | YOLOv8 by Benax, used as-is (not retrained) |
| 1 | Quality gate (is the photo readable?) | MobileNetV2 (about 2.2 M parameters), ImageNet-pretrained, fine-tuned; threshold 0.429 chosen on validation; used as a **soft prompt only** |
| 2 | Read the 8 wheels | CRNN (CNN + BiLSTM + CTC, Shi et al.) compared with **ResNet18 + BiGRU + CTC** (selected, "E4") |
| 3 | Anomaly check | Isolation Forest + deterministic rules, per household history |

Reader input: grayscale, 64 × 256 px, 32 output columns over 11 symbols (0–9 + CTC blank).
Augmentation: brightness/contrast, small rotation/shift/zoom-out, light blur; **no random erasing**
(it hid whole digits and caused invented digits).
Training: AdamW, warm-up then cosine learning rate, gradient clipping at 5, best epoch kept on
validation, frozen CNN for the first fine-tuning epochs.

Experiments (all judged on the same validation set):

| ID | Starts from | Trains on | Question |
|---|---|---|---|
| E1 | random | Kigali only | Can about 310 Kigali photos alone teach the model? |
| E2 | Yandex-pretrained CRNN | Kigali | Does pretraining help? |
| E3 | Yandex-pretrained CRNN | Kigali + Yandex ("rehearsal") | Does mixing reduce overfitting? |
| E4 | ImageNet ResNet18 + BiGRU, Yandex-pretrained | Kigali + Yandex | Alternative architecture (selected) |

Baselines: **EasyOCR** (off-the-shelf OCR) for reading; a **Laplacian blur threshold** for the
quality gate. Model selection rule written before testing: best validation per-meter accuracy;
candidates within 3 points are equal; then fewer parameters.

**[FILL IN from the committed Kaggle run]**: the validation and test table for EasyOCR, the
Yandex-only model, E1, E2, E3, E4; the domain-gap number (Yandex model on Kigali before
fine-tuning); the quality-gate AUCs (blur baseline, MobileNetV2 v1, v2 with synthetic damage,
reader confidence). The repository copy of the notebook has no saved outputs, so these numbers
must come from the Kaggle version.

Metrics: exact match; **reading accuracy** (headline, ignores leading zeros); **per-meter
accuracy** (each meter counts once); edit distance; within one digit; length errors; **95%
confidence interval by meter-level bootstrap** (2,000 resamples of whole meters).

### 5.4 Anomaly detection (Stage 3)

Features are relative to the household's own past, per day: `days_since_last`, consumption,
`daily_consumption`, `ratio_to_median`, `robust_z` (median/MAD based), `ratio_to_recent`,
`n_history`. The model uses log-transformed ratios. One shared Isolation Forest (200 trees,
contamination 0.05, random_state 42) for all households, because one household has too few
readings for its own model.

Rules run first and always:

| Condition | Result |
|---|---|
| First reading | BASELINE (never an anomaly) |
| Lower than the previous reading | MISREAD_SUSPECTED (meters cannot run backwards) |
| Daily use above 5 m³ | SPIKE |
| Zero use for 30+ days | METER_STUCK |
| Fewer than 3 previous periods | cold start: rules only |

Model anomalies are named in order: a ratio near 10× or 100× means MISREAD_SUSPECTED (shifted digit),
a ratio of 3× or more means SPIKE, three high periods in a row means SUSTAINED_HIGH, and anything
else is UNUSUAL. MISREAD_SUSPECTED and SPIKE readings, and anything below the last confirmed reading,
are **held** (not billed) for an officer. The others are billed but flagged.

**Important:** no real WASAC reading histories were available, so the Isolation Forest was only
trained and evaluated on **synthetic DEMO households**. Those numbers must **not** be reported as
real results. The deployed service runs **rules only** (`/health` reports
`rules_only_model_not_trained`). State this as a limitation and as future work.

---

## 6. System design

### 6.1 Architecture

```
Household phone (PWA, React)         WASAC staff (browser, React)
        │  HTTPS                              │
        ▼                                     ▼
   Vercel (static app) ──────────►  Render: FastAPI (Docker, ONNX Runtime)
                                      │   YOLOv8 → MobileNetV2 → ResNet18+BiGRU → rules/IF
                                      ├─► Neon PostgreSQL (households, meters, readings, bills,
                                      │     flags, payments, photos, staff, audit log)
                                      ├─► Africa's Talking (SMS, USSD)
                                      └─► MTN MoMo Collections (payments; simulated without keys)
```

### 6.2 Technology stack

| Layer | Tools |
|---|---|
| Frontend | React 18, Vite, strict TypeScript, CSS Modules, design tokens, own i18n (Kinyarwanda default, English), PWA (manifest, service worker, offline shell, install prompt), Lucide icons |
| Backend | Python 3.10, FastAPI, SQLAlchemy 2.0, Pydantic v2, ONNX Runtime (serving), PyTorch (training/export), OpenCV, Pillow, scikit-learn |
| Data | PostgreSQL on Neon (production), SQLite (local and tests) |
| Integrations | Africa's Talking SMS and USSD; MTN MoMo Collections (Request to Pay); Web Push (VAPID) |
| Training | Kaggle notebook (GPU), `notebooks/wasac_meter_reading_pipeline.ipynb` |
| Quality | pytest, Vitest + React Testing Library, GitHub Actions CI, Playwright live end-to-end script |
| Hosting | Render (API, Docker), Vercel (app), Neon (database), all free tiers |

Code size (tracked files): about 5,200 lines of backend Python (`backend/app`), 7,700 lines of
TypeScript/TSX and 4,100 lines of CSS in the frontend.

### 6.3 Users and main flows

**Household (phone):** sign in with the phone number and a 6-digit SMS code (no password) →
Read (camera with live framing tips) → photo is read and shown on a meter counter → household
checks or corrects the 8 digits → confirm → either billed at once, or "we're checking this
reading" → bill → pay with MTN MoMo → receipt by SMS; history; messages; optional phone alerts.

**USSD (any phone):** menu in Kinyarwanda first: send a reading, see the latest bill, pay,
switch language.

**Staff (laptop):** sign in (roles officer < supervisor < admin) → overview → review queue (photo,
the reader's digits, whether the household edited them, history chart, location check;
keyboard shortcuts, 5-second undo) → accept (bills it) or reject (household asked to read again,
by SMS) → activity log (every action audited) → households (unpaid totals, meter correction) →
staff accounts (temporary passwords, forced change) → sent SMS (sandbox outbox).

### 6.4 Business rules

- One reading per billing period: the next opens **25 days** after an accepted reading; only one
  reading may wait for review at a time.
- **Location check:** the phone's position at photo time is compared with the meter's; more
  than 150 m away, imprecise, missing, or a gallery upload means held for review. The first precise
  camera photo an officer accepts sets the meter's location.
- Tariff (from the project brief; to be confirmed with WASAC/RURA): 0–5 m³ RWF 350/m³; 6–15 m³
  RWF 530; 16–30 m³ RWF 791; over 30 m³ RWF 1,000; plus RWF 1,000 service charge.
- Photos kept for reviewers for 90 days, then deleted; unconfirmed photos deleted after a day.

---

## 7. Implementation (what to describe and show)

Key components and where they are (good for screenshots of code):

| Topic | File |
|---|---|
| Photo pipeline (crop, guidance, gate, reader) | `backend/app/vision/pipeline.py`, `onnx_models.py` |
| Reading a meter value strictly | `backend/app/utils/meter_value.py` |
| Submitting a reading (locking, rules, billing) | `backend/app/anomaly/service.py` (`submit_reading`) |
| Anomaly rules and model | `backend/app/anomaly/rules.py`, `features.py`, `model.py` |
| Officer decisions | `backend/app/anomaly/review.py` (`resolve_flag`) |
| Tariff | `backend/app/services/billing.py` |
| Mobile money | `backend/app/services/momo.py`, `payments.py` |
| SMS / USSD | `backend/app/services/sms.py`, `ussd_menu.py` |
| Sign-in and tokens | `backend/app/core/security.py`, `backend/app/api/routes/household_auth.py` |
| Meter counter UI | `frontend/src/components/MeterCounter/MeterCounter.tsx` |
| Camera with live tips | `frontend/src/pages/CameraCapture/CameraCapture.tsx` |
| Review queue | `frontend/src/pages/staff/ReviewQueue.tsx` |

Engineering decisions worth explaining:
- **ONNX Runtime for serving.** PyTorch did not fit a 512 MB free server. The three models were
  exported to ONNX; on 150 real photos plus 12 synthetic ones the ONNX and PyTorch versions gave the
  same detections (boxes within 4 px), the same digits and the same retake decisions.
- **Model files are private.** `best.pt` belongs to Benax and may not be redistributed; the reader
  and gate are non-commercial (trained partly on CC BY-NC-ND data). The server downloads them at
  start from private links and checks SHA-256 checksums.
- **Never block the household.** Every guidance tip is a soft prompt. If the models are missing,
  the household types the numbers instead.
- **Security:**
  - PBKDF2 password hashing.
  - HMAC-signed tokens carrying a password stamp, so a password change ends old sessions.
  - Lockout after 5 failed sign-ins.
  - One-time codes stored only as keyed hashes, with per-IP and per-phone rate limits.
  - USSD callback protected by a secret token.
  - Strict numeric validation.
  - Row locks and a unique bill per reading, so retries or two officers cannot bill twice.
  - Staff-only access to photos.

## 8. Testing

| Kind | What | Result |
|---|---|---|
| Backend unit and integration tests | pytest, in-memory database, fake models (212 test functions, 271 cases) | all passing |
| Frontend tests | Vitest + React Testing Library (170 tests in 30 files) | all passing |
| Continuous integration | GitHub Actions runs both suites on every push; nothing goes live unless green | passing |
| Live end-to-end test | `tools/e2e/live_e2e.mjs`, Playwright on the deployed site with a real meter photo, 18 steps (sign-in, camera, upload, confirm, held, review with photo, accept, activity, households, SMS, accounts, bill, pay, history, messages, 25-day rule) | 18/18, 0 problems (27/10/2026) |
| Model tests | Locked test set once (Section 9); ONNX vs PyTorch parity on 150+12 photos | see Section 9 |
| Guidance calibration | 652 meter photos + 1,182 non-meter images (`docs/calibration/guidance_calibration.md`) | thresholds chosen by written rules |
| Accessibility | Colour contrast computed (WCAG AA on every text/background pair), keyboard use, screen-reader labels, reduced motion | met |
| Security review | Self-review against a findings list: USSD bypass, numeric input, follow-up flags, session revocation, drafts per account, idempotency | all fixed and tested |

**[FILL IN] User testing / feedback:** who tried the app (fellow students, family, supervisor,
any WASAC contact), what they said, and what changed as a result. Changes driven by feedback
that can be cited from the project history:
- **Visual design:** redesigned several times, from a navy serif design, through a rejected
  "imigongo" redesign, back to the navy design, then to an editorial "Navy and Ink" system with
  Josefin Sans and professional Lucide icons.
- **Name:** renamed to Mubazi.
- **Mobile layout:** fixes for the phone layout, the status-bar area and the floating bottom bar.
- **Dark mode:** fixed.
- **Back button and demo label:** a clearer back button, and the "demo data" label removed.

## 9. Results (real numbers only)

**Meter reader (selected model E4, ResNet18 + BiGRU), locked Kigali test set: 79 photos, 34 meters**

| Metric | Value |
|---|---|
| Reading accuracy (leading zeros ignored) | **55.7%** |
| Per-meter reading accuracy | 55.74% |
| 95% CI (meter-level bootstrap) | **42–69%** |
| Correct or within one digit | **70.9%** |

**Photo guidance calibration** (652 WASAC photos; readable vs unreadable flag rates):

| Check | Threshold | Readable flagged | Unreadable flagged |
|---|---|---|---|
| HARD_TO_READ (quality gate) | P(unreadable) ≥ 0.50 | 8.4% | 83.7% |
| CHECK_NUMBERS (reader confidence) | lowest digit < 0.50 | 9.7% | 32.7% |
| NO_METER (window confidence) | 0.35 | 1.1% | 11.2% |

Non-meter images wrongly taken as meters: 0.5% of 1,132 patches, 0% of 50 COCO images. Blur
checking was turned off: it fired more on readable photos (dirty glass adds texture). On photos
never used in training, HARD_TO_READ still separates the groups (11% vs 60%) but CHECK_NUMBERS barely
does (15% vs 20%).

**Performance (deployed, Render free CPU):** about 0.7 s per live framing tip; 1.3–3.7 s to read a
photo on the server; about a minute for the first request after the free server sleeps.

**System:** full household-to-staff-to-payment flow works on the live deployment (18/18 steps).

## 10. Discussion and limitations

- **Accuracy is moderate** (55.7%, CI 42–69%). This is why the design keeps a human in the loop:
  every reading is shown to the household to confirm, and suspicious ones go to an officer. Most
  near misses are a single digit, often the last litre wheel caught mid-turn, which barely changes a
  bill.
- **Small data:** 536 readable Kigali readings, 34 test meters; wide confidence intervals; the
  validation and test sets can differ by 10–20 points by chance.
- **Domain gap:** Yandex (Russian) meters differ from Kigali meters; pretraining helps but does not
  remove the gap. **[FILL IN the before/after numbers]**
- **Quality gate is data-limited** (fewer than 100 real unreadable photos), so it is a soft prompt.
- **Anomaly model not validated on real data;** production runs rules only.
- **Integrations in test mode:** Africa's Talking sandbox (SMS reach the simulator and the staff
  outbox, not real phones); MTN MoMo simulated until developer keys are added; USSD channel and
  phone alerts need setup keys.
- **Licensing:** YOLOv8 weights from Benax (no redistribution), Yandex data non-commercial; a
  commercial WASAC deployment would need its own training data and licences. Ultralytics is
  AGPL-3.0.
- **Free hosting:** cold starts and slow CPU.
- **Kinyarwanda text:** drafted, awaiting review by a native speaker.
- **Tariff:** taken from the project brief; needs confirmation against the official WASAC/RURA
  tariff.

## 11. Recommendations and future work

1. Collect more Kigali meter photos, especially unreadable ones, with WASAC's consent; retrain the
   reader and the quality gate; aim for a larger test set with narrower confidence intervals.
2. Train and validate the Isolation Forest on real WASAC reading histories.
3. Replace third-party weights with a window detector trained on WASAC-owned data.
4. Move integrations to live accounts: MTN MoMo production, an Africa's Talking live sender ID,
   a USSD short code.
5. Pilot with a small group of households and officers; measure time per reading, disputes and
   detected leaks.
6. Run the models on the phone (MobileNetV2 is small enough) for instant feedback offline.
7. Native-speaker review of all Kinyarwanda; add French.
8. Paid hosting for speed and reliability; monitoring.

## 12. Ethics, privacy and data

- Photos and locations are personal data. Photos are visible only to staff, kept 90 days, then
  deleted. Location is used only to check the photo was taken at the meter, never shared.
- One-time codes and passwords are never stored in plain text; SMS logs mask phone numbers.
- Training data used with permission (Benax, for academic use) or under its licence (Yandex,
  CC BY-NC-ND 4.0, non-commercial).
- Demo households in the live system are clearly prefixed DEMO- and use invented data.
- **[FILL IN]** Any consent obtained from testers; ALU ethics guidance followed.

## 13. Screenshots to include (take them from the live app)

1. Landing page (desktop and phone).
2. Household sign-in with the code screen.
3. Camera with the live framing guide.
4. Confirm reading screen with the meter counter.
5. "We're checking this reading" screen.
6. Home with the bill card and the bottom navigation.
7. Bill detail and the payment receipt.
8. Messages (a decision).
9. Staff overview.
10. Review queue with the photo, the reader's digits and the location check.
11. Activity log.
12. Households table and meter correction.
13. Dark mode example.
14. Code: `submit_reading` in `service.py`, the rules in `rules.py`, the pipeline in
    `pipeline.py`, a test file, and the CI run on GitHub.
15. Diagram: the architecture in Section 6.1, plus the model pipeline in Section 5.3.
16. Charts from the notebook: training curves, validation table, error analysis, quality-gate ROC
    **[FILL IN from Kaggle]**.

## 14. Mapping to the rubric

| Rubric criterion | Where the content is in this brief |
|---|---|
| Abstract (intro, objectives, method, findings, conclusions, recommendations) | Sections 2, 3, 5, 9, 10, 11; write it last, about 250–300 words |
| Incorporation of feedback | Section 8, user feedback **[FILL IN supervisor comments and what changed]** |
| Formatting | ALU template: cover page, declaration, dedication/acknowledgements, abstract, table of contents, list of figures/tables, abbreviations (roman page numbers); chapters in arabic numbering |
| System implementation and testing | Sections 6, 7, 8, 13 |
| Results and discussion | Sections 9, 10, linked to the research questions in Section 4 |
| Conclusions and recommendations | Sections 10, 11 (answer each research question in one paragraph) |
| Writing mechanics | Clear chapter flow: introduction → literature → methodology → design and implementation → testing and results → discussion → conclusion |
| Relevant literature | Section 15 themes; compare with related meter-reading and anomaly work |
| References | Section 15; APA 7; every in-text citation in the list and vice versa |
| Plagiarism | Rule 3 in Section 0 |

Suggested abbreviations: AI, API, AUC, CI, CNN, CRNN, CTC, GRU, LSTM, MAD, MoMo, OCR, ONNX, OTP, PWA,
RURA, RWF, SMS, USSD, WASAC, YOLO.

## 15. Literature themes and real sources to look up (verify each before citing)

| Theme | Sources to find and check |
|---|---|
| Text recognition with CRNN | Shi, Bai and Yao (2016), end-to-end trainable network for image-based sequence recognition, *IEEE TPAMI* |
| CTC loss | Graves, Fernández, Gomez and Schmidhuber (2006), Connectionist Temporal Classification, *ICML* |
| ResNet | He, Zhang, Ren and Sun (2016), Deep residual learning for image recognition, *CVPR* |
| GRU | Cho et al. (2014), learning phrase representations using RNN encoder–decoder, *EMNLP* |
| MobileNetV2 | Sandler et al. (2018), MobileNetV2: inverted residuals and linear bottlenecks, *CVPR* |
| YOLO / YOLOv8 | Redmon et al. (2016), You Only Look Once, *CVPR*; Jocher et al., Ultralytics YOLOv8 (software, 2023) |
| Isolation Forest | Liu, Ting and Zhou (2008), Isolation Forest, *IEEE ICDM* |
| Robust statistics (median, MAD) | Leys et al. (2013), detecting outliers: use absolute deviation around the median, *Journal of Experimental Social Psychology* |
| Bootstrap confidence intervals | Efron (1979), Bootstrap methods, *Annals of Statistics*; Efron and Tibshirani (1993), *An Introduction to the Bootstrap* |
| Transfer learning | Pan and Yang (2010), A survey on transfer learning, *IEEE TKDE* |
| Automatic meter reading from images | Search Google Scholar for "automatic meter reading deep learning" (for example the UFPR-AMR work by Laroca et al.); pick 2–4 recent, verified papers |
| Water anomaly / leak detection from consumption | Search "water consumption anomaly detection smart meter"; pick 2–3 verified papers |
| Mobile money and digital services in Rwanda / Africa | GSMA *State of the Industry Report on Mobile Money*; NISR or RURA statistics |
| Accessibility | W3C (2018), *Web Content Accessibility Guidelines (WCAG) 2.1* |
| Datasets | Yandex Toloka water meters dataset (find its official page and licence); Benax Rwandan meter model (cite as personal communication / model page) |

Only cite what the student has actually read and can link to.
