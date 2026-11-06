# Operating the prototype

Current evidence uses synthetic accounts. This document prepares operational steps; it does not
certify a production service or authorize using real participant/customer data.

## Database configuration

Set `DATABASE_URL` in the deployment environment. `APP_ENV=production` or Render's `RENDER` flag makes
missing configuration a startup error. Local development defaults to `sqlite:///./local.db`.
PostgreSQL uses five pooled connections plus two overflow connections per worker, a 10-second pool
wait and a 10-second connect timeout. `pool_pre_ping` checks stale connections before reuse. Additional
workers multiply this budget; measure before changing it. Never print the environment or connection string.

## Schema revisions

Startup calls Alembic `upgrade head` before serving traffic. `0001` creates missing baseline tables
and indexes while retaining existing tables; `0002` adds the known legacy columns. PostgreSQL uses a
transaction-level advisory lock so application workers cannot migrate at once. Duplicate financial
records that prevent a unique index cause startup to fail rather than silently losing the safeguard.

From `backend/`, with the correct environment and a verified backup:

```sh
python -m alembic current
python -m alembic upgrade head
```

Do not use `stamp head` to hide schema differences. Future changes need new reviewed revisions, plus
tests against both a fresh database and an existing one. The baseline's downgrade intentionally
refuses to drop financial tables; rollback uses the verified backup and previous application version.
The implementation follows Alembic's [connection-sharing interface](https://alembic.sqlalchemy.org/en/latest/api/config.html).

## Photo retention

Confirmed images expire after `PHOTO_RETENTION_DAYS` (default 90); unconfirmed photo records expire
after a day. Cleanup runs on upload and at API startup, then every
`PHOTO_CLEANUP_INTERVAL_SECONDS` (default 3600, minimum 60) while the process is awake. It preserves
the linked reading/financial records when removing expired image bytes.

Because free hosting sleeps, configure an independent daily scheduler with the same environment:

```sh
cd backend
python scripts/purge_photos.py
```

Deletion is performed at the next cleanup run, not guaranteed at the exact age threshold. A daily
scheduler introduces up to its interval of delay. The 90-day application policy is different from
the proposal's three-month-after-study research policy; obtain approval for the actual data plan.

## Monitoring

Use `GET /health/ready` for an external uptime monitor: 200 means the database answered; 503 means it
did not. `GET /health` is liveness and can return 200 with degraded state. It also reports whether
photo recognition is ready or only manual entry is available. A healthy database does not guarantee
recognition or provider availability. Configure alerts for readiness failures, model degradation,
failed cleanup and migration errors. Store uptime observations before claiming the 99% pilot target.

## Backup and recovery

Before the first migration deployment, create a Neon recovery point/backup using the account's
available facilities and verify its restore procedure. Do not paste the connection string into
source, chat, screenshots or logs. Set a backup frequency and retention window with the project owner.
Preserve the application commit and schema revision alongside each backup. Restrict access to dumps.

For an authorized PostgreSQL database, PostgreSQL 16 tools can make a custom-format dump. With
standard `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE`, `PGPASSWORD` and TLS variables supplied securely:

```sh
pg_dump --format=custom --file=/secure/backup/location/mubazi.dump
```

Restore into a **separate empty test database** using its own connection settings:

```sh
pg_restore --no-owner --no-acl --dbname=mubazi_restore_test /secure/backup/location/mubazi.dump
```

Compare table counts, `alembic_version`, original bill amounts, adjustments, successful payments,
credits and resulting balances. Check login and a read-only staff journey on the restored copy.
Do not overwrite the live database during a drill. Store backups outside the public repository.

On 6 November a local PostgreSQL 16 drill successfully restored all table counts, 40 synthetic
customers, 960 readings, schema revision 0002, a RWF 1,000 bill and a RWF 500 successful payment.
This verifies that local example, not Neon recovery or real customer data.

## Release evidence

Run the supported Python 3.10 CI jobs, frontend typecheck/tests/build, PostgreSQL races and three
browser engines for the submitted commit. Current local results and their environment limits are in
`docs/testing/README.md`. Actual phones, provider delivery/settlement and independent security review
remain external validation. Pushing `main` deploys: take the backup and review scope/configuration first.
