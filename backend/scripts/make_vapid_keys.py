"""Make the key pair for phone alerts (web push), once, and add it to backend/.env.

    python scripts/make_vapid_keys.py

Writes VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY to backend/.env (gitignored) unless they are already
there. Prints only the public key; copy both values from .env to Render's environment. Making a
new pair later stops every phone's alerts until it turns them on again.
"""
import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

ENV = Path(__file__).resolve().parent.parent / ".env"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def main() -> None:
    existing = ENV.read_text() if ENV.exists() else ""
    if "VAPID_PRIVATE_KEY=" in existing and "VAPID_PRIVATE_KEY=\n" not in existing:
        print("backend/.env already has VAPID keys; nothing changed.")
        return
    key = ec.generate_private_key(ec.SECP256R1())
    private = b64url(key.private_numbers().private_value.to_bytes(32, "big"))
    public = b64url(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
    with ENV.open("a") as f:
        f.write(f"\n# Phone alerts (web push), made by scripts/make_vapid_keys.py\nVAPID_PUBLIC_KEY={public}\nVAPID_PRIVATE_KEY={private}\n")
    print(f"Added to backend/.env. Public key: {public}")
    print("Copy VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY from backend/.env to Render.")


if __name__ == "__main__":
    main()
