from datetime import date, timedelta


def date_today() -> date:
    return date.today()


def current_week(today: date) -> tuple[date, date]:
    monday = today - timedelta(days=today.weekday())
    return monday, monday + timedelta(days=6)
