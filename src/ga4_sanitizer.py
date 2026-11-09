"""Step 3 - THE PRIVACY BOUNDARY. Turns an internal event into a GA4-safe event.

Allowed to leave:  action, module, surface, channel, tenant_hash   (nothing else, ever)

How the boundary is enforced (defence in depth):
  1. ALLOWLIST  - the safe event is built from scratch by reading exactly 4 input fields.
                  We never "delete the bad fields" from the original; a new sensitive field
                  added next year therefore cannot leak by accident.
  2. CLOSED VALUES - action/module/surface/channel are Enums. Free text (a company name)
                  cannot be put in them.
  3. STRICT MODEL - SafeEvent forbids extra fields (extra="forbid") and is immutable.
  4. KEYED HASH - tenant IDs are hashed with HMAC-SHA256 and a secret key, so they cannot be
                  reversed by guessing IDs (plain hashes of short IDs can be brute-forced).
  5. FAIL CLOSED - an event with no entry in EVENT_MAP raises an error and is not exported.
  6. ONE DOOR   - to_measurement_protocol() only accepts a SafeEvent, nothing else.
  (The database repeats the rules with CHECK constraints, see sql/01_schema.sql,
   and tests/test_boundary.py attacks all of this with planted "canary" values.)
"""
import hashlib
import hmac
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .taxonomy import EVENT_MAP, Action, Channel, Module, Surface

GA4_EVENT_NAME = "app_action"  # one generic GA4 event; the details travel as parameters


class UnmappedEventError(ValueError):
    """Raised when an internal event has no entry in the tracking plan."""


class SafeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: Action
    module: Module
    surface: Surface
    channel: Channel
    tenant_hash: str = Field(pattern=r"^[0-9a-f]{32}$")


def hash_tenant(tenant_id: str, key: bytes) -> str:
    """Keyed, one-way, deterministic: same tenant + same key -> same hash, so GA4 can still
    count 'how many different companies'. Truncated to 32 hex chars (128 bits)."""
    return hmac.new(key, tenant_id.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def sanitize(raw: Mapping[str, Any], key: bytes) -> SafeEvent:
    """Build the safe version of one internal event.

    Only these raw fields are ever read: event_name, tenant_id, surface, channel.
    The module is taken from the tracking plan, not from the raw row, so a wrong
    raw value cannot change what we send.
    """
    try:
        action, module = EVENT_MAP[raw["event_name"]]
    except KeyError as exc:
        raise UnmappedEventError("event is not in the tracking plan; refusing to export") from exc

    return SafeEvent(
        action=action,
        module=module,
        surface=raw["surface"],
        channel=raw["channel"],
        tenant_hash=hash_tenant(str(raw["tenant_id"]), key),
    )


def to_measurement_protocol(event: SafeEvent) -> dict:
    """Shape of the JSON GA4's Measurement Protocol accepts. This POC only BUILDS the payload
    (a dry run). It deliberately sends nothing over the network.

    client_id = tenant_hash, so GA4's 'users' equal 'companies'. (Check current GA4 docs for
    parameter naming and length limits before wiring up a real property.)
    """
    if not isinstance(event, SafeEvent):
        raise TypeError("only a SafeEvent may be turned into a GA4 payload")
    p = event.model_dump(mode="json")
    return {
        "client_id": p["tenant_hash"],
        "events": [{"name": GA4_EVENT_NAME,
                    "params": {k: p[k] for k in ("action", "module", "surface", "channel", "tenant_hash")}}],
    }
