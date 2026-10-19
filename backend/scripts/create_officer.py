"""Create a staff account, or reset its password.

    python scripts/create_officer.py <username> --name "Full Name" [--role admin]

Roles: officer (reviews readings), supervisor (also sees everyone's
activity), admin (also manages staff accounts in the dashboard). Create
the first admin with this script; admins add everyone else from the
dashboard. Running it for an existing username resets the password (and
the role, if --role is given).

The password is asked for (twice) and never echoed or stored in shell
history. Use --password-stdin to pipe it in from a secrets manager.
"""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import ROLES, StaffUser  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import Base, SessionLocal, engine  # noqa: E402

MIN_LENGTH = 10


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("username")
    parser.add_argument("--name", help="Full name shown in the dashboard (required for a new account)")
    parser.add_argument("--role", choices=ROLES, help="officer (default for a new account), supervisor or admin")
    parser.add_argument("--password-stdin", action="store_true", help="Read the password from standard input")
    args = parser.parse_args()

    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            print("The passwords do not match.", file=sys.stderr)
            return 1
    if len(password) < MIN_LENGTH:
        print(f"Use at least {MIN_LENGTH} characters.", file=sys.stderr)
        return 1

    Base.metadata.create_all(bind=engine)
    username = args.username.strip().lower()
    db = SessionLocal()
    try:
        user = db.query(StaffUser).filter(StaffUser.username == username).first()
        if user:
            user.password_hash = hash_password(password)
            user.is_active = True
            if args.name:
                user.full_name = args.name
            if args.role:
                user.role = args.role
            action = "Password reset for"
        else:
            if not args.name:
                print("--name is required for a new account.", file=sys.stderr)
                return 1
            db.add(StaffUser(username=username, full_name=args.name, role=args.role or "officer",
                             password_hash=hash_password(password)))
            action = "Created"
        db.commit()
    finally:
        db.close()
    print(f"{action} {username}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
