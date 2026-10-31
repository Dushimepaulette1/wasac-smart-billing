# Supervisor check-in: script and demo plan

About 10 minutes of talking and demo, then questions. Say it in your own words; the lines below are
a guide, not something to read out word for word.

## Before the meeting (do these the day before)

1. **Re-run the notebook on Kaggle** ("Save Version → Save & Run All"; about 50–70 minutes on a GPU)
   so the new learning-curve plots exist. Download these from the output:
   `learning_curves_readers.png`, `learning_curves_quality_gate.png`, `learning_curve_gaps.csv`,
   `final_test_results.csv`, `train_kigali_experiments.png`.
   - A new run gives slightly different numbers (GPU training is not perfectly repeatable). Either
     keep the deployed models and say "the curves come from a re-run with the same recipe", or, if
     you switch to the new weights, update `backend/ml/model_config.json` and the report so every
     number comes from one run.
2. **Wake the server** 5 minutes before: open https://wasac-api.onrender.com/health (the free server
   sleeps; the first request takes about a minute).
3. Have three tabs open:
   - the app on your phone, or a phone-sized browser window;
   - the staff dashboard on the laptop (`/staff`, signed in);
   - the Kaggle notebook, at the learning curves.
4. Pick a demo household that can send a reading today: that has not read in the last 25 days. Households 001 to 018 were used
   recently, so ask for fresh demo households first.
5. Have a clear photo of a meter ready on the phone, in case the camera is awkward in the room.

---

## Script

### 1. Where I am (30 seconds)

"Since our last meeting, the system is complete and deployed. Households can read their meter with a
photo, the AI reads the digits, the reading is checked against the household's own history, and
suspicious readings go to a WASAC officer before any bill is made. Payment, SMS and USSD are built;
SMS and payment run in test mode until I get live accounts. I've also added the learning curves you
asked for."

### 2. The problem in one line (20 seconds)

"WASAC meters are read by hand. That's slow and leads to estimated bills, misread digits and leaks
found late. Mubazi lets the household read the meter itself, and keeps a person in the loop where
the AI is unsure."

### 3. The learning curves (2 minutes) — show the notebook

Open section **11.3 Learning curves**.

- "Each row is one model. Left: training and validation loss per epoch. Right: training and
  validation accuracy. The dashed line is the epoch I kept, the best on validation."
- **E1 (from scratch):** "It sits flat for the first epochs. That's the CTC 'blank' plateau, where the
  model predicts nothing, before it starts reading. With only about 310 Kigali photos it learns
  slowly."
- **E2 (fine-tuned):** "Pretraining on the Yandex meters lets it start much higher. But the gap
  between training and validation opens quickly, which means it overfits the few Kigali meters."
- **E3 / E4 (mixed with Yandex):** "Mixing Yandex images into every batch keeps the gap smaller.
  That's why I used it for the final model. E4, ResNet18 with a BiGRU, was the one selected."
- Show the **gap table** (`learning_curve_gaps.csv`): "This puts a number on overfitting:
  training minus validation accuracy at the kept epoch." **[Read your actual numbers here.]**
- **Quality gate curves:** "Training AUC climbs well above validation. With only 68 real unreadable
  training photos the gate is data-limited, so in the app it's a soft hint that never blocks the
  household."

### 4. Results (1 minute)

"On the locked test set, 79 photos of 34 meters the model never saw, the selected reader gets
**55.7%** of readings fully right (95% confidence interval 42–69%) and **70.9%** right or within one
digit. That's not good enough to bill automatically, which is why every reading is confirmed by the
household and suspicious ones go to an officer. Most near misses are the last litre wheel caught
mid-turn, worth a few litres."

### 5. Live demo (5 minutes): see the next section

### 6. What's left and my questions (1–2 minutes)

"What's left: real SMS and MoMo accounts, a Kinyarwanda review by a native speaker, and the report.
The anomaly model is only trained on demo data, because I don't have real WASAC reading histories,
so the live system uses the rules only. I'll present that as a limitation."

Questions to ask her:
1. "Is 55.7% with a human-in-the-loop design acceptable as a result if I discuss it honestly, or
   should I spend the remaining time trying to raise it?"
2. "For the anomaly detection, is evaluation on synthetic data acceptable if it's clearly labelled,
   or should I find real or realistic reading histories?"
3. "Do the learning curves show what you wanted, or would you like other plots, such as a confusion
   matrix or per-digit errors?"
4. "Anything in the report structure you'd like me to change before I submit on 6 November?"

---

## Demo order (about 5 minutes)

Keep it to one clear story: **a household reads its meter, an officer checks it, the household
pays.**

| # | Where | What to do | What to say |
|---|---|---|---|
| 1 | Phone | Open the landing page, scroll once | "This is Mubazi, built as an installable web app so it works on cheap phones and slow data." |
| 2 | Phone | **Sign in** with 0700 000 009; the code appears on screen | "Households sign in with their phone number and an SMS code. No password. Demo numbers show the code on screen because the SMS is in sandbox mode." |
| 3 | Phone | Tap the raised **Read** button; point at the meter (or upload the photo) | "The camera gives live tips like 'move closer' or 'too dark'. None of them block the household." |
| 4 | Phone | The confirm screen shows the 8 wheels | "Three models ran on the server: YOLO finds the number window, MobileNetV2 checks quality, and the ResNet-BiGRU reader reads the digits. The household checks them and can correct any digit." |
| 5 | Phone | **Confirm** → "We're checking this reading" | "This reading looked unusual against the household's history, so it isn't billed. It goes to an officer." (If it bills straight away instead, say it was normal and skip to step 9.) |
| 6 | Laptop | Staff **Review queue** | "The officer sees the photo, what the AI read, whether the household changed it, where the photo was taken, and the household's usual use." |
| 7 | Laptop | **Accept** (point out the 5-second undo) | "Accepting creates the bill and sends an SMS." |
| 8 | Laptop | **Activity**, then **Sent SMS** | "Every decision is recorded. And here is the SMS the household would get." |
| 9 | Phone | Home shows the banner "Your reading was accepted" and the bill | — |
| 10 | Phone, then laptop | **Pay**: dial the code, enter a transaction ID; on the laptop open **Payments** and confirm; the phone shows Paid | "Without MTN's API, the household pays WASAC's MoMo Pay code and gives the transaction ID. A bill is only paid once an officer finds it in WASAC's MoMo account. With the API keys, MTN confirms it automatically." |
| 11 | Phone | Tap Read again | "One reading per month: the next one opens in 25 days." |

**If there is time:**
- Switch to dark mode, then to Kinyarwanda.
- On the laptop, show **Households → Correct a meter reading**.
- Show the GitHub Actions page, where every change runs about 450 automated tests.

**If something goes wrong:**
- **The server is slow:** say "it's on a free server that sleeps" and wait; it's usually ready
  within a minute.
- **The photo isn't read:** tap "Type the numbers instead". That's the designed fallback, so say so.
- **No internet:** use the screenshots in `docs/design/screenshots/` or the report.

## Likely questions and short answers

- **Why is accuracy only 55.7%?** "The dataset is small: 536 readable Kigali readings, and 34 test
  meters, so the confidence interval is wide. Kigali meters look different from the Yandex meters I
  pretrained on. The design keeps people in the loop because of this."
- **How do you know it's not overfitting?** "The test set was split by meter, so no meter appears
  in both training and test. It was used once, after the model was chosen. The learning curves show
  the overfitting gap, and rehearsal with Yandex images reduces it."
- **What does the anomaly detection actually do live?** "Rules, run first: a lower reading than
  last time, more than 5 m³ a day, or no use for 30 days. The Isolation Forest is ready but trained
  only on demo data. With real histories it would be retrained with the same scripts."
- **Is it really deployed?** "Yes: Vercel for the app, Render for the API with ONNX Runtime, Neon for
  Postgres. An automated test runs the whole journey on the live site."
- **What about privacy?** "Photos are visible only to staff, kept 90 days, then deleted. Codes and
  passwords are never stored in plain text."
