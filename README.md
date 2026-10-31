# Mubazi: read your water meter with your phone

**Mubazi** means "water meter" in Kinyarwanda. It is a web app that helps households in Kigali, Rwanda
send their water meter reading to WASAC with a phone photo. WASAC is Rwanda's water utility.

This is a capstone project by Dushime Paulette at the African Leadership University. It is a
working prototype and **is not an official WASAC service**. All the households in it are made up.

| | |
|---|---|
| **Try the app** | https://wasac-smart-billing-qt9t.vercel.app |
| **Staff area** | https://wasac-smart-billing-qt9t.vercel.app/staff |
| **Walkthrough video** | [FILL IN: video link] |
| **Technical report (PDF)** | [docs/report/Mubazi_Technical_Report.pdf](docs/report/Mubazi_Technical_Report.pdf) |
| **GitHub repository** | https://github.com/Dushimepaulette1/wasac-smart-billing |

The app runs on free servers. If it has not been used for a while, the first request can take about a
minute while the server wakes up.

## The problem

Many meters in Kigali are analog: the numbers sit on small rolling wheels, and a person has to read
them. When readings are late or wrong, a household can get a surprise bill, and WASAC has to spend
time checking it. Mubazi tests a simpler way: the household takes a photo, AI helps read it, and
people stay in control of the final number.

## How it works

1. A household signs in with their phone number and a 6-digit code.
2. They take a photo of the meter.
3. AI reads the numbers from the photo.
4. The household checks the numbers and fixes any that are wrong.
5. Mubazi checks that the reading makes sense.
6. If it looks normal, the bill appears straight away.
7. If it looks unusual, a WASAC officer looks at it first.
8. The household pays the bill, and staff confirm the payment.

**The AI helps, but people decide.** On photos it had never seen, the AI read 55.7% of meters fully
correctly (95% confidence interval: 42 to 69%). That is not enough to trust alone, so a person always
checks the numbers.

## Who uses it

| Person | What they can do |
|---|---|
| **Household** | Send a reading, see bills and history, pay, read messages, use Kinyarwanda or English |
| **Officer** | Accept or reject unusual readings, add or edit households, check payments |
| **Supervisor** | Everything an officer does, plus upload customer lists, make corrections, approve other people's corrections |
| **Admin** | Everything a supervisor does, plus manage staff accounts and read sent SMS messages |

Nobody can create their own household account. Staff add households, because a household must match
a real WASAC customer and meter. Later, WASAC's own records could be connected through a data-sharing
agreement.

## When a reading is held for an officer

A reading waits for an officer if any of these is true:

- It is lower than the last reading.
- It is about 3 times the household's usual use or more, or more than 5 m³ a day.
- It is the meter's first reading, so there is nothing to compare it with.
- The household lowered a reliable AI reading by 1 m³ or more.
- The meter passed 99,999 and started again.
- The photo was uploaded, or was not taken near the meter's saved location.

The officer sees the photo, the AI's digits, the household's digits, past use and the location, then
accepts or rejects. These limits are starting estimates, not values tested on WASAC's real data.

## What is real and what is simulated

| Part | Status |
|---|---|
| Web app, database, photo reading, rules, bills, officer review | Working and live |
| Households and meters | Made up, marked as demo data |
| Water prices | Provisional, to be confirmed with WASAC and RURA |
| SMS messages | Test mode only, so real phones do not receive them. Sign-in codes for demo households appear on screen |
| Payments | No real money moves. Staff check payments by hand, against a test list if one is uploaded |
| USSD menu for basic phones | Built and tested, but not on a live phone channel |
| Isolation Forest (the anomaly model) | Tested on simulated data only, so the live app uses rules |

## Try it

### As a household

1. Open the [app](https://wasac-smart-billing-qt9t.vercel.app).
2. Sign in with a demo number from **0700 000 021** to **0700 000 026**.
3. Copy the code shown on screen.
4. Follow the steps to send a reading.

Each demo household can send one reading every 25 days, so a number you use may already be taken.

### As staff

Staff accounts are private. To see the staff screens, run the project on your computer and create
your own admin account (steps below), or watch the walkthrough video.

## Run it on your computer

### What you need

| Tool | Version |
|---|---|
| Python | 3.10 |
| Node.js | 22 |
| Git | Any recent version |
| Database | SQLite for a quick try (nothing to install), PostgreSQL 16 for the full setup |
| Hardware | A normal laptop. The live server runs on 512 MB of memory |

### 1. Get the code

```bash
git clone https://github.com/Dushimepaulette1/wasac-smart-billing.git
cd wasac-smart-billing
```

### 2. Start the backend

Open a terminal in the project folder:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # On Windows: copy .env.example .env
```

Open `backend/.env` and change the `DATABASE_URL` line to this:

```
DATABASE_URL=sqlite:///./local.db
```

Then add some demo households, create your admin account and start the server:

```bash
python scripts/demo/generate_demo_households.py --load-db
python scripts/create_officer.py admin --name "Your Name" --role admin
uvicorn app.main:app --reload
```

The second command asks you to choose a password. Leave the third one running. The backend is now at
http://localhost:8000, and http://localhost:8000/docs lists its API.

### 3. Start the frontend

Open a second terminal in the project folder:

```bash
cd frontend
npm install
npm start
```

Open http://localhost:3000 for the household app, or http://localhost:3000/staff for the staff area.

### Photo reading

The AI model files are private and are not in this repository, partly because one belongs to Benax.
Without them, the app still works: it asks the household to type the numbers.

### Run the tests

```bash
cd backend && pytest             # backend tests
cd frontend && npm test          # frontend tests
```

## What is in this project

```
wasac-smart-billing/
├── backend/         The server (Python and FastAPI)
│   ├── app/         API routes, billing, payments, checks and photo reading
│   ├── ml/          Code that runs the AI models
│   ├── simulation/  Offline test of anomaly detection, using made-up data
│   ├── scripts/     Helpers, such as adding demo households
│   └── tests/       Backend tests
├── frontend/        The website (React and TypeScript)
│   ├── src/         Pages, components and the Kinyarwanda and English text
│   └── tests/       Frontend tests
├── notebooks/       The notebook that trained the AI models
├── docs/            Report, testing evidence and technical notes
└── tools/           End-to-end browser test and load test
```

## How it was tested

| Test | Result |
|---|---|
| Automated backend tests | 569 passed, 5 skipped, 94% of lines covered |
| Automated frontend tests | 232 passed, 83% of lines covered |
| Full journey on the live site, in a real browser | 25 of 25 steps passed |
| Page checks in Chromium, Firefox and WebKit at four screen sizes | 36 of 36 passed |
| Load test on a local copy | No errors with 50 users at once |
| Anomaly detection on simulated data | The forest scored F1 0.89 and the rules 0.50. This is synthetic data, not evidence of real performance |

The full results are in [docs/testing](docs/testing/README.md).

## Installing it on a phone

Mubazi is a web app you can install, so there is no APK file. Open the link on your phone and choose
**Install** or **Add to Home Screen**.

## Learn more

- [Technical guide](docs/TECHNICAL_GUIDE.md): how each part works, settings and deployment
- [Algorithms](docs/ALGORITHMS.md): the main problems solved, and the simulation results
- [Open items](docs/decisions/OPEN_ITEMS.md): what still needs WASAC, MTN or another decision

## Licence and limits

This is an academic project. The AI models are for **non-commercial academic use only**, because they
were trained partly on the Yandex water meter dataset (CC BY-NC-ND 4.0). Details are in the
[technical guide](docs/TECHNICAL_GUIDE.md).
