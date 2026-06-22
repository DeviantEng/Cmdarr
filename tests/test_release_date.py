from datetime import date

from utils.release_date import (
    parse_release_date,
    release_date_within,
    release_within_bounds,
    release_within_cutoff,
)


def test_parse_release_date_formats():
    assert parse_release_date("2024-05-15") == date(2024, 5, 15)
    assert parse_release_date("2024-05") == date(2024, 5, 1)
    assert parse_release_date("2024") == date(2024, 1, 1)
    assert parse_release_date("") is None


def test_release_date_within_recent():
    today = date.today()
    assert release_date_within(today.isoformat(), "30d") is True
    assert release_date_within("1999-01-01", "30d") is False
    assert release_date_within(f"{today.year}-01-15", "this_year") is True
    assert release_date_within("2019-12-31", "this_year") is False


def test_release_date_within_previous_year():
    prev = date.today().year - 1
    assert release_date_within(f"{prev}-06-15", "previous_year") is True
    assert release_date_within(f"{prev}", "previous_year") is True
    assert release_date_within(f"{prev}-12-31", "previous_year") is True
    assert release_date_within(f"{prev + 1}-01-01", "previous_year") is False
    assert release_date_within(f"{prev - 1}-12-31", "previous_year") is False


def test_release_date_within_all():
    assert release_date_within("1999-01-01", "all") is True
    assert release_date_within(None, "all") is True


def test_release_within_bounds():
    today = date.today()
    start, end = release_within_bounds("this_year")
    assert start == date(today.year, 1, 1)
    assert end is None

    prev = today.year - 1
    start, end = release_within_bounds("previous_year")
    assert start == date(prev, 1, 1)
    assert end == date(prev, 12, 31)


def test_release_within_cutoff_this_year():
    cutoff = release_within_cutoff("this_year")
    assert cutoff == date(date.today().year, 1, 1)
