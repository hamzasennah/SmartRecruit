from app.database.models import Base
from app.database.session import get_engine


engine = get_engine()
if engine is None:
    print("DATABASE_URL absent ou SQLAlchemy indisponible.")
else:
    Base.metadata.create_all(bind=engine)
    print("Tables initialisees.")

