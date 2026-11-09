from datetime import datetime, timezone

from src.generate_events import generate_events

END = datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_same_seed_gives_same_data():
    a = generate_events(seed=1, tenants=5, days=28, end=END)
    b = generate_events(seed=1, tenants=5, days=28, end=END)
    assert a == b


def test_every_paid_bill_was_received_first():
    events = generate_events(seed=2, tenants=10, days=56, end=END)
    received = {e["bill_id"]: e["occurred_at"] for e in events if e["event_name"] == "bill_received"}
    paid = {e["bill_id"]: e["occurred_at"] for e in events if e["event_name"] == "bill_paid"}
    assert paid, "expected some paid bills"
    for bill_id, paid_at in paid.items():
        assert bill_id in received and received[bill_id] <= paid_at  # ISO strings sort correctly


def test_contains_duplicates_and_only_bill_events_have_bill_id():
    events = generate_events(seed=3, tenants=10, days=56, end=END)
    ids = [e["event_id"] for e in events]
    assert len(ids) > len(set(ids))   # duplicates were injected on purpose
    for e in events:
        assert (e["bill_id"] is not None) == (e["event_name"] in ("bill_received", "bill_paid"))
