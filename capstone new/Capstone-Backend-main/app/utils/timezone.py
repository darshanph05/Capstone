from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo


CANBERRA_TZ = ZoneInfo("Australia/Sydney")


def now_canberra_naive() -> datetime:
    return datetime.now(CANBERRA_TZ).replace(tzinfo=None)


def to_canberra_naive(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(CANBERRA_TZ).replace(tzinfo=None)