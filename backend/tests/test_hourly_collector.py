from datetime import datetime
from zoneinfo import ZoneInfo

from app.workers.hourly_collector import next_hourly_run

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def test_hourly_schedule_uses_next_shanghai_hour_boundary() -> None:
    assert next_hourly_run(datetime(2026, 10, 27, 11, 22, 7, tzinfo=SHANGHAI_TZ)) == datetime(
        2026, 10, 27, 12, 0, tzinfo=SHANGHAI_TZ
    )


def test_hourly_schedule_does_not_repeat_an_already_reached_boundary() -> None:
    assert next_hourly_run(datetime(2026, 10, 27, 12, 0, tzinfo=SHANGHAI_TZ)) == datetime(
        2026, 10, 27, 13, 0, tzinfo=SHANGHAI_TZ
    )
