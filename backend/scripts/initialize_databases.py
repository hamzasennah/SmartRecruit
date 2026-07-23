from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database.models import Base
from app.database.session import get_engine


engine = get_engine()
Base.metadata.create_all(bind=engine)
print("Tables initialisees.")
