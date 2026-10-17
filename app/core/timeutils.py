from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.core.config import settings

TZ = ZoneInfo(settings.timezone)


def now() -> datetime:
    return datetime.now(TZ)


def localize(dt: datetime) -> datetime:
    """Interpreta fechas sin zona horaria como hora local del salón."""
    return dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt


def to_local(dt: datetime) -> datetime:
    return localize(dt).astimezone(TZ)


def local_datetime(day: date, at: time) -> datetime:
    return datetime.combine(day, at, tzinfo=TZ)
