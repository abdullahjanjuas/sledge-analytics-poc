"""Attack tests for the GA4 boundary. These are the most important tests in the project.

Idea: plant 'canary' values (obviously fake sensitive data) in the input, then prove that
none of them can be found anywhere in what would be sent to GA4.
"""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.ga4_sanitizer import (SafeEvent, UnmappedEventError, hash_tenant, sanitize,
                               to_measurement_protocol)
from src.taxonomy import EVENT_MAP, Action, Channel, Module, Surface

KEY = b"unit-test-key-not-a-real-secret-123"

CANARY = {
    "event_id": "0b0f3b9e-0000-4000-8000-000000000001",
    "event_name": "invoice_created",
    "occurred_at": "2026-10-01T10:15:00Z",
    "tenant_id": "ten_CANARYTENANT777",
    "company_name": "ZXQ-CANARY Plumbing LLC",
    "counterparty_name": "ZXQ-CANARY Supply Co.",
    "counterparty_tax_id": "99-9999999",
    "amount": 123456.78,
    "days_to_pay": 31.5,
    "bill_id": None,
    "module": "invoices",
    "surface": "web",
    "channel": "in_app",
    "bank_account": "000123456789",     # a field nobody planned for: must still not leak
}


def serialized(event: SafeEvent) -> str:
    return json.dumps(to_measurement_protocol(event)) + event.model_dump_json()


def test_output_has_exactly_the_five_allowed_fields():
    out = sanitize(CANARY, KEY).model_dump(mode="json")
    assert set(out) == {"action", "module", "surface", "channel", "tenant_hash"}


def test_canary_values_never_appear_in_output():
    text = serialized(sanitize(CANARY, KEY))
    for forbidden in ["CANARY", "ZXQ", "99-9999999", "123456", "31.5",
                      "000123456789", "ten_", "Plumbing", "Supply", "$"]:
        assert forbidden not in text, f"leaked: {forbidden}"


def test_unplanned_new_sensitive_field_cannot_leak():
    """Allowlist proof: adding more fields to the raw event changes nothing."""
    a = sanitize(CANARY, KEY)
    b = sanitize({**CANARY, "ssn": "123-45-6789", "email": "x@y.com"}, KEY)
    assert a == b


def test_extra_fields_are_rejected_by_the_model():
    base = dict(action="create", module="invoices", surface="web", channel="in_app", tenant_hash="a" * 32)
    SafeEvent(**base)  # fine
    for extra in ({"amount": 5}, {"company_name": "X"}, {"duration_days": 3}, {"tax_id": "1"}):
        with pytest.raises(ValidationError):
            SafeEvent(**base, **extra)


def test_free_text_is_rejected_in_categorical_fields():
    with pytest.raises(ValidationError):
        SafeEvent(action="create", module="Apex Plumbing LLC", surface="web",
                  channel="in_app", tenant_hash="a" * 32)


def test_unmapped_event_fails_closed():
    with pytest.raises(UnmappedEventError):
        sanitize({**CANARY, "event_name": "brand_new_event"}, KEY)


def test_hash_is_deterministic_keyed_and_not_the_raw_id():
    h1 = hash_tenant("ten_1", KEY)
    assert h1 == hash_tenant("ten_1", KEY)                       # same input -> same output
    assert h1 != hash_tenant("ten_2", KEY)                       # different tenants differ
    assert h1 != hash_tenant("ten_1", b"a-different-secret-key")  # the key matters
    assert len(h1) == 32 and "ten_1" not in h1


def test_payload_builder_only_accepts_safe_events():
    with pytest.raises(TypeError):
        to_measurement_protocol(CANARY)  # a raw dict must be refused


def test_every_payload_value_is_a_short_string_never_a_number():
    for event_name in EVENT_MAP:
        for surface in Surface:
            for channel in Channel:
                raw = {**CANARY, "event_name": event_name, "surface": surface.value, "channel": channel.value}
                params = to_measurement_protocol(sanitize(raw, KEY))["events"][0]["params"]
                assert all(isinstance(v, str) and len(v) <= 100 for v in params.values())


def test_python_enums_match_sql_constraints():
    """If someone adds a value in Python but forgets the database (or vice versa), fail."""
    sql = (Path(__file__).resolve().parents[1] / "sql" / "01_schema.sql").read_text()
    for enum in (Action, Module, Surface, Channel):
        for member in enum:
            assert f"'{member.value}'" in sql, f"{member.value} missing from sql/01_schema.sql"
    for name in EVENT_MAP:
        assert f"'{name}'" in sql
