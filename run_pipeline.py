"""
Steps (same as `make pipeline`):
  1. create tables + views in Postgres      (runs the .sql files)
  2. generate fake events -> data/events.jsonl
  3. validate + load them into Postgres
  4. build the GA4-safe events
"""
from src import apply_sql, export_ga4, generate_events, load_events


def step(title: str) -> None:
    print(f"\n=== {title} ===")


step("1/4 Create tables and views")
apply_sql.main(["sql/01_schema.sql", "sql/02_views.sql"])

step("2/4 Generate fake events")
generate_events.main()

step("3/4 Load events into Postgres")
load_events.main()

step("4/4 Build GA4-safe events")
export_ga4.main()

print("\nDONE. Next: run run_dashboard.py")
