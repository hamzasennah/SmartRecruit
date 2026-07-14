from app.config import settings


def get_engine():
    if not settings.database_url:
        return None
    from sqlalchemy import create_engine
    return create_engine(settings.database_url, pool_pre_ping=True)

