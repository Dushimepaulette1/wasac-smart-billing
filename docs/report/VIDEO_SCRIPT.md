# Walkthrough video script (about 10 to 12 minutes)

Before recording: wake https://wasac-api.onrender.com/health, open the app on a phone, `/staff` on the laptop, GitHub Actions,
and `docs/testing/`. Use a demo household whose reading is free. Say it in your own words.

| Time | Show | Say |
|---|---|---|
| 0:00 | Landing page | The problem: manual reading and estimated bills. Mubazi lets households read their own meter, with a person in the loop. |
| 0:45 | Architecture in the README | React calls FastAPI; FastAPI runs ONNX models, rules and PostgreSQL. Vercel, Render, Neon. |
| 1:30 | Scope table in the report | What was planned, built, changed, and what was not done and why. |
| 2:30 | Sign in on the phone | SMS code, stored hashed, limited tries. Accounts come from WASAC's records: staff add or upload them. |
| 3:15 | Read the meter | Live tips never block. YOLO finds the window, MobileNetV2 checks quality, ResNet18 + BiGRU with CTC reads the digits. |
| 4:15 | Confirm a normal reading | The check runs before sending. The bill comes from the tiered tariff. |
| 5:00 | Wrong inputs: a lower value, then a much higher one | The check explains why it would be held, and keeps the numbers so the household can fix them. |
| 6:00 | Staff review queue | True previous reading, photo, changed wheels, location. Accept has an undo; reject needs a reason. |
| 6:45 | Pay by MoMo Pay: bad ID, good ID, staff confirm | Never marked paid until checked. Explain how WASAC verifies a payment. |
| 7:30 | Bill correction with a second approver; CSV preview with a mistake | Originals are never overwritten. |
| 8:15 | USSD; Kinyarwanda and dark mode | Basic phones, and language. |
| 8:45 | GitHub Actions, coverage, race tests | Strategy 1: why, how, results, what changed. |
| 9:30 | The end-to-end check running | Strategy 2: why, how, results, what changed. |
| 10:00 | `compatibility.md`, `load.md`, real phone results | Browsers, sizes, slow phones, load. Say which are simulated. |
| 11:00 | `payment_providers.py`, `onnx_models.py`, folders | OOP: abstraction, polymorphism, separation of concerns. |
| 11:30 | Results and limits | 55.7% (CI 42 to 69%), why people stay in the loop, rules only live, sandbox SMS. |
