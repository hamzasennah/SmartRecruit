from app.config import settings


def database_enabled() -> bool:
    return bool(settings.database_url)

