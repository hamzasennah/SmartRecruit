import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        check=False,
    )
    if result.returncode == 0:
        print("Migrations appliquees.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

# Role dans le projet:
# Ce script initialise les migrations de base. Il prepare PostgreSQL/pgvector avant les tests ou l'execution locale du backend.
