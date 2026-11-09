"""Step 4 - build the GA4-safe copy of every event.   Run: python -m src.export_ga4

Data minimisation: we SELECT only the 4 columns the sanitizer needs. Amounts, company
names, party names and tax IDs are never even loaded into this script's memory.
"""
import json
from pathlib import Path

from pydantic import ValidationError

from .config import get_hash_key
from .db import connect
from .ga4_sanitizer import UnmappedEventError, sanitize, to_measurement_protocol

SAMPLE_FILE = Path("samples/ga4_events_sample.jsonl")


def main() -> None:
    key = get_hash_key()
    safe, dropped = [], 0

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT event_name, tenant_id, surface, channel FROM internal.events ORDER BY occurred_at")
        for event_name, tenant_id, surface, channel in cur.fetchall():
            try:
                safe.append(sanitize({"event_name": event_name, "tenant_id": tenant_id,
                                      "surface": surface, "channel": channel}, key))
            except (UnmappedEventError, ValidationError):
                dropped += 1   # fail closed: anything we cannot cleanly map is not exported

        cur.execute("TRUNCATE ga4.outbox RESTART IDENTITY")   # the outbox is derived data: rebuild it
        cur.executemany(
            "INSERT INTO ga4.outbox (action, module, surface, channel, tenant_hash) VALUES (%s,%s,%s,%s,%s)",
            [(e.action.value, e.module.value, e.surface.value, e.channel.value, e.tenant_hash) for e in safe],
        )

    SAMPLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SAMPLE_FILE.open("w", encoding="utf-8") as f:     # a small sample reviewers can open
        for e in safe[:25]:
            f.write(json.dumps(to_measurement_protocol(e)) + "\n")

    print(f"exported {len(safe)} GA4-safe events | dropped {dropped} unmappable events")
    print(f"sample payloads written to {SAMPLE_FILE}")


if __name__ == "__main__":
    main()
