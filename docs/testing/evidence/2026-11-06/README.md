# Local validation, 6 November 2026

Base commit: `0c9eba1`; results apply to the modified working tree prepared for submission, not a claim
that this base commit contains these fixes. Environment: macOS 27.2, Python 3.9.6, Node 22.23.4,
PostgreSQL 16 in Docker. The actual production image also passed the full suite on Linux Python 3.10.22; GitHub CI remains required for the submitted commit.

- `backend.txt`: 617 passed, 5 skipped; 94.10% line coverage. Includes 16 PostgreSQL checks.
- `backend-python310.txt`: 617 passed, 5 skipped in the actual Linux Python 3.10.22 serving image with test-only dependencies; 94% coverage.
- `compatibility.md`: 36/36 checks in the official Linux Playwright container; simulated screens/networks.
- `journey.txt`: 25/25 local synthetic journey checkpoints, zero problems; manual-entry fallback, no private model weights.
- `frontend.txt`: 262 passed; 83.36% line coverage. Typecheck and production build also passed.
- `backup-restore.txt`: synthetic PostgreSQL dump/restore drill. No Neon data used.
- `load.md`: endpoint load only, one local SQLite API worker; not simultaneous photo inference.

The downloaded macOS browsers were killed when launched, and installed Chrome timed out. These
attempts are not counted as compatibility passes. The subsequent Linux Docker run is the successful
three-engine and journey evidence above; historical live results remain separate.

The model weights and real provider keys were not used. No live accounts or payments were changed.
