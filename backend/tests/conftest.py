from __future__ import annotations

import os

# Tests run against the live DB inside the backend container (via `make test`). Default DB
# connection settings are inherited from the environment.

os.environ.setdefault("POSTGRES_HOST", "postgres")
os.environ.setdefault("AUTO_SEED", "false")
