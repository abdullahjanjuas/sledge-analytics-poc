"""Step 2 - validate events and load them into PostgreSQL.   Run: python -m src.load_events

Two protections:
  1. Validation: every line must match the RawEvent shape. Bad lines are counted and
     skipped, not loaded.
  2. Idempotency: INSERT ... ON CONFLICT DO NOTHING on event_id, so running the loader
     twice (or loading duplicate events) never creates duplicate rows.
"""
import argparse
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .db import connect
from .taxonomy import EVENT_MAP, Channel, Module, Surface


class RawEvent(BaseModel):
    """The contract for an incoming internal event. Unknown extra fields are rejected."""
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    event_name: str
    occurred_at: datetime
    tenant_id: str = Field(min_length=1)
    company_name: str = Field(min_length=1)
    counterparty_name: str | None = None
    counterparty_tax_id: str | None = None
    amount: Decimal = Field(ge=0)
    bill_id: str | None = None
    module: Module
    surface: Surface
    channel: Channel

    @field_validator("event_name")
    @classmethod
    def known_event(cls, v: str) -> str:
        if v not in EVENT_MAP:
            raise ValueError("unknown event_name")
        return v

    @field_validator("occurred_at")
    @classmethod
    def must_have_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("occurred_at must include a timezone (store everything in UTC)")
        return v


INSERT_SQL = """
INSERT INTO internal.events
  (event_id, event_name, occurred_at, tenant_id, company_name, counterparty_name,
   counterparty_tax_id, amount, bill_id, module, surface, channel)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (event_id) DO NOTHING
"""


def read_valid_events(path: Path) -> tuple[list[RawEvent], int]:
    good, bad = [], 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                good.append(RawEvent.model_validate_json(line))
            except ValidationError:
                bad += 1
    return good, bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="data/events.jsonl")
    args = ap.parse_args()

    events, rejected = read_valid_events(Path(args.file))
    rows = [(e.event_id, e.event_name, e.occurred_at, e.tenant_id, e.company_name, e.counterparty_name,
             e.counterparty_tax_id, e.amount, e.bill_id, e.module.value, e.surface.value, e.channel.value)
            for e in events]

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM internal.events")
        before = cur.fetchone()[0]
        for i in range(0, len(rows), 1000):          # insert in batches of 1000
            cur.executemany(INSERT_SQL, rows[i:i + 1000])
        cur.execute("SELECT count(*) FROM internal.events")
        after = cur.fetchone()[0]

    print(f"read {len(events) + rejected} lines | valid {len(events)} | rejected {rejected}")
    print(f"inserted {after - before} new rows | skipped {len(events) - (after - before)} duplicates | table now has {after}")


if __name__ == "__main__":
    main()
