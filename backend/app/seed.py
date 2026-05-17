"""Auto-seed the transactions table on startup if it is empty and AUTO_SEED is true.

Filled out by coding task 4. This stub exists so the container CMD `python -m app.seed`
succeeds before the importer is in place.
"""
from __future__ import annotations


def main() -> None:
    try:
        from .services.importer import maybe_auto_seed

        maybe_auto_seed()
    except Exception as exc:  # noqa: BLE001
        # Don't fail container startup if seed fails — the API can still serve /health and the user
        # can import manually.
        print(f"[seed] non-fatal: {exc}")


if __name__ == "__main__":
    main()
