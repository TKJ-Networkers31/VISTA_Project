from datetime import datetime, timedelta, timezone

import pytest

from core.routing import CallBudget


def test_budget_counts_and_blocks():
    b = CallBudget(2)
    assert b.acquire() and b.acquire() and not b.acquire()
    assert b.used() == 2 and b.remaining() == 0


def test_budget_resets_on_a_new_utc_day():
    now = [datetime(2026, 10, 10, 23, 59, tzinfo=timezone.utc)]
    b = CallBudget(1, clock=lambda: now[0])
    assert b.acquire() and not b.acquire()
    now[0] += timedelta(minutes=2)
    assert b.acquire()


def test_budget_rejects_bad_limit():
    with pytest.raises(ValueError):
        CallBudget(0)
