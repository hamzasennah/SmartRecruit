from app.database.models import Base
from app.database.session import get_engine


engine = get_engine()
Base.metadata.create_all(bind=engine)
print("Tables initialisees.")
