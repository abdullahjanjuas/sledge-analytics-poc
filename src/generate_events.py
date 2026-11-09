"""Step 1 - make believable fake events for a fictional construction-software company.

Run:  python -m src.generate_events --tenants 40 --days 84 --seed 42

Design choices (so the data tells a story, not random noise):
  * tenants (customer companies) sign up gradually  -> weekly active companies grows
  * each tenant has its own activity level and "pay speed" -> realistic differences
  * every bill_received can later produce a bill_paid (same bill_id), after a
    realistic delay; some bills are still unpaid (open) at the end
  * ~1% of events are re-sent (duplicates) and the file is shuffled, like real pipelines
"""
import argparse
import json
import math
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from faker import Faker

from .taxonomy import EVENT_MAP

PREFIXES = ["Apex", "Ironclad", "Summit", "Blue Ridge", "Keystone", "Granite", "Northstar", "Redwood",
            "Pioneer", "Cornerstone", "Silverline", "Bedrock", "Highland", "Lakeside", "Anchor",
            "Evergreen", "Falcon", "Harbor", "Titan", "Crescent", "Meridian", "Sterling", "Beacon"]
TRADES = ["Plumbing", "Electric", "Roofing", "Concrete", "HVAC", "Framing", "Masonry", "Drywall",
          "Excavation", "Painting", "Flooring", "Builders"]
SUFFIXES = ["LLC", "Inc.", "Co.", "Group"]

# how often each (non-paid) event type happens. bill_paid is created from bill_received.
EVENT_WEIGHTS = {"bill_received": 0.38, "invoice_created": 0.26, "lien_waiver_uploaded": 0.20,
                 "contract_signed": 0.08, "change_order_approved": 0.08}

# typical amount per event type: (median dollars, spread)
AMOUNT_PROFILE = {"bill_received": (6_000, 1.1), "invoice_created": (15_000, 1.0),
                  "lien_waiver_uploaded": (8_000, 1.0), "contract_signed": (90_000, 0.9),
                  "change_order_approved": (12_000, 0.9)}

SURFACE_WEIGHTS = {"web": 0.70, "mobile": 0.25, "api": 0.05}
CHANNEL_WEIGHTS = {  # bills usually arrive by email or an integration; the rest are done in the app
    "bill_received":         {"email": 0.55, "integration": 0.25, "in_app": 0.20},
    "bill_paid":             {"in_app": 0.50, "integration": 0.40, "email": 0.10},
    "invoice_created":       {"in_app": 0.75, "integration": 0.20, "email": 0.05},
    "lien_waiver_uploaded":  {"in_app": 0.50, "email": 0.40, "integration": 0.10},
    "contract_signed":       {"in_app": 0.70, "email": 0.30, "integration": 0.00},
    "change_order_approved": {"in_app": 0.80, "email": 0.20, "integration": 0.00},
}


def pick(rng: random.Random, weights: dict[str, float]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()), k=1)[0]


def poisson(rng: random.Random, lam: float) -> int:
    """Small helper: random count of events with average `lam` (Knuth's method)."""
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def new_uuid(rng: random.Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))  # seeded -> reproducible


def make_tenants(rng: random.Random, fake: Faker, n: int, days: int) -> list[dict]:
    used, tenants = set(), []
    for i in range(n):
        while True:
            name = f"{rng.choice(PREFIXES)} {rng.choice(TRADES)} {rng.choice(SUFFIXES)}"
            if name not in used:
                used.add(name)
                break
        tenants.append({
            "tenant_id": f"ten_{rng.getrandbits(40):010x}",
            "company_name": name,
            # first 5 tenants are there from day 0, the rest join over time
            "start_day": 0 if i < 5 else rng.randint(0, int(days * 0.9)),
            "events_per_workday": rng.choice([1.0, 2.0, 2.0, 4.0, 7.0]),
            "pay_speed": rng.choice([0.6, 1.0, 1.0, 1.0, 1.6]),   # >1 = slower payer
            "counterparties": [(fake.company(), f"{rng.randint(10, 99)}-{rng.randint(1000000, 9999999)}")
                               for _ in range(8)],
        })
    return tenants


def make_timestamp(rng: random.Random, day: datetime) -> datetime:
    hour = int(rng.triangular(6, 20, 11))  # most activity mid-morning
    return day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59), microsecond=0)


def make_amount(rng: random.Random, event_name: str) -> float:
    median, spread = AMOUNT_PROFILE[event_name]
    return round(min(max(rng.lognormvariate(math.log(median), spread), 150), 400_000), 2)


def generate_events(seed: int = 42, tenants: int = 40, days: int = 84,
                    end: datetime | None = None, duplicate_rate: float = 0.01) -> list[dict]:
    rng = random.Random(seed)
    Faker.seed(seed)
    fake = Faker("en_US")
    end = end or datetime.now(timezone.utc)
    start = (end - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)

    events: list[dict] = []

    def add(event_name, ts, tenant, party, amount, bill_id=None):
        module = EVENT_MAP[event_name][1].value
        events.append({
            "event_id": new_uuid(rng),
            "event_name": event_name,
            "occurred_at": ts.isoformat().replace("+00:00", "Z"),
            "tenant_id": tenant["tenant_id"],
            "company_name": tenant["company_name"],
            "counterparty_name": party[0],
            "counterparty_tax_id": party[1],
            "amount": amount,
            "bill_id": bill_id,
            "module": module,
            "surface": pick(rng, SURFACE_WEIGHTS),
            "channel": pick(rng, CHANNEL_WEIGHTS[event_name]),
        })

    active_weeks: dict[tuple[str, int], bool] = {}
    for tenant in make_tenants(rng, fake, tenants, days):
        for d in range(tenant["start_day"], days + 1):
            day = start + timedelta(days=d)
            if day > end:
                break
            week = d // 7
            key = (tenant["tenant_id"], week)
            if key not in active_weeks:                      # ~12% of weeks a tenant is quiet
                active_weeks[key] = rng.random() > 0.12
            if not active_weeks[key] or day.weekday() >= 5:  # nothing on weekends
                continue
            for _ in range(poisson(rng, tenant["events_per_workday"])):
                name = pick(rng, EVENT_WEIGHTS)
                ts = make_timestamp(rng, day)
                if ts > end:
                    continue
                party = rng.choice(tenant["counterparties"])
                amount = make_amount(rng, name)
                if name == "bill_received":
                    bill_id = f"bill_{rng.getrandbits(32):08x}"
                    add("bill_received", ts, tenant, party, amount, bill_id)
                    if rng.random() < 0.88:                   # 12% of bills never get paid in our window
                        median_days = 21 * tenant["pay_speed"]
                        paid_ts = ts + timedelta(days=rng.lognormvariate(math.log(median_days), 0.5))
                        if paid_ts <= end:                    # otherwise still open "today"
                            add("bill_paid", paid_ts.replace(microsecond=0), tenant, party, amount, bill_id)
                else:
                    add(name, ts, tenant, party, amount)

    dupes = [dict(e) for e in rng.sample(events, int(len(events) * duplicate_rate))]
    events.extend(dupes)      # same event_id sent twice -> the loader must cope
    rng.shuffle(events)       # real events do not arrive in order
    return events


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tenants", type=int, default=40)
    ap.add_argument("--days", type=int, default=84, help="how many days of history (84 = 12 weeks)")
    ap.add_argument("--seed", type=int, default=42, help="same seed -> same data")
    ap.add_argument("--out", default="data/events.jsonl")
    args = ap.parse_args()

    events = generate_events(seed=args.seed, tenants=args.tenants, days=args.days)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    names = {}
    for e in events:
        names[e["event_name"]] = names.get(e["event_name"], 0) + 1
    print(f"wrote {len(events)} events to {out}")
    for k, v in sorted(names.items(), key=lambda kv: -kv[1]):
        print(f"  {k:24s}{v}")


if __name__ == "__main__":
    main()
