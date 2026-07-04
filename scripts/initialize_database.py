"""Initialize the local SQLite database."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.database import create_tables, engine


def main() -> None:
    """Create required folders and database tables."""

    settings = get_settings()
    if settings.database_path is not None:
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    create_tables(engine)
    print("Base de datos inicializada correctamente.")


if __name__ == "__main__":
    main()
