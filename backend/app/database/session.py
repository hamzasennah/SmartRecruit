from app.config import settings
from app.core.exceptions import ExternalServiceError


def get_engine():
    if not settings.database_url:
        raise ExternalServiceError("DATABASE_URL est obligatoire pour utiliser PostgreSQL.")
    from sqlalchemy import create_engine
    return create_engine(settings.database_url, pool_pre_ping=True)

# Role dans le projet:
# Ce fichier construit le moteur et les sessions SQLAlchemy generiques. Il sert aux composants qui veulent acceder directement a PostgreSQL.
