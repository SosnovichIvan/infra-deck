"""Forward-only, transactional, advisory-lock serialized migration runner."""

from pathlib import Path

from infradeck.config import Settings
from infradeck.db import Database


def migrate(db: Database, directory: Path) -> None:
    with db.transaction() as tx:
        tx.execute("SELECT pg_advisory_xact_lock(482819150)")
        tx.execute("CREATE TABLE IF NOT EXISTS schema_versions (version text PRIMARY KEY)")
        for path in sorted(directory.glob("*.sql")):
            if not tx.execute(
                "SELECT 1 FROM schema_versions WHERE version=%s", (path.name,)
            ).fetchone():
                tx.execute(path.read_text())
                tx.execute("INSERT INTO schema_versions VALUES (%s)", (path.name,))


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    migrate(
        Database(settings.database_url.get_secret_value()),
        Path(__file__).resolve().parent / "migrations",
    )


if __name__ == "__main__":
    main()
