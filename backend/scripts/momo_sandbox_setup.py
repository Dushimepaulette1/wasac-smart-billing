"""Create the MTN MoMo sandbox API user and key, and save them in backend/.env.

    1. On momodeveloper.mtn.com: sign up, subscribe to "Collections", copy its Primary key.
    2. Add it to backend/.env:   MOMO_SUBSCRIPTION_KEY=<primary key>
    3. python scripts/momo_sandbox_setup.py

The script asks MTN for a new API user and key (sandbox only) and appends MOMO_API_USER and
MOMO_API_KEY to backend/.env. Nothing secret is printed. Then copy the three MOMO_ values into
Render (Environment) and redeploy.
"""
import os
import sys
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
BASE = os.getenv("MOMO_BASE_URL", "https://sandbox.momodeveloper.mtn.com").rstrip("/")
CALLBACK_HOST = "wasac-api.onrender.com"


def main() -> int:
    load_dotenv(ENV_FILE)
    key = os.getenv("MOMO_SUBSCRIPTION_KEY", "").strip()
    if not key:
        print("Add MOMO_SUBSCRIPTION_KEY=<Collections primary key> to backend/.env first.")
        return 1
    if os.getenv("MOMO_API_USER") and os.getenv("MOMO_API_KEY"):
        print("backend/.env already has MOMO_API_USER and MOMO_API_KEY; nothing to do.")
        return 0
    user = str(uuid.uuid4())
    headers = {"Ocp-Apim-Subscription-Key": key}
    r = httpx.post(f"{BASE}/v1_0/apiuser", json={"providerCallbackHost": CALLBACK_HOST},
                   headers={**headers, "X-Reference-Id": user}, timeout=20)
    if r.status_code != 201:
        print(f"MTN refused to create the API user (HTTP {r.status_code}). Check the subscription key "
              "is the Collections product's primary key.")
        return 1
    r = httpx.post(f"{BASE}/v1_0/apiuser/{user}/apikey", headers=headers, timeout=20)
    if r.status_code != 201:
        print(f"MTN refused to create the API key (HTTP {r.status_code}).")
        return 1
    api_key = r.json()["apiKey"]
    with open(ENV_FILE, "a") as f:
        f.write(f"\n# MTN MoMo sandbox (scripts/momo_sandbox_setup.py)\nMOMO_API_USER={user}\nMOMO_API_KEY={api_key}\n")
    print("Done: MOMO_API_USER and MOMO_API_KEY were added to backend/.env.")
    print("Copy MOMO_SUBSCRIPTION_KEY, MOMO_API_USER and MOMO_API_KEY from backend/.env into Render.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
