"""Print summary of generated_events.jsonl after a pipeline run."""

import json
import sys
from collections import Counter
from pathlib import Path


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/generated_events.jsonl")
    events = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]
    customers = [e for e in events if not e["is_staff"]]
    print(f"File: {path}")
    print(f"Total events: {len(events)}")
    print(f"Customer events: {len(customers)}")
    print(f"Staff-tagged: {len(events) - len(customers)}")
    print(f"Event types (all): {dict(Counter(e['event_type'] for e in events))}")
    print(f"Event types (customers): {dict(Counter(e['event_type'] for e in customers))}")
    print(f"Unique visitors (customers): {len({e['visitor_id'] for e in customers})}")
    entries = sum(1 for e in customers if e["event_type"] in ("ENTRY", "REENTRY"))
    exits = sum(1 for e in customers if e["event_type"] == "EXIT")
    print(f"Customer ENTRY+REENTRY: {entries}  EXIT: {exits}")
    print(f"Zones (customers): {dict(Counter(e.get('zone_id') for e in customers if e.get('zone_id')))}")
    if events:
        print(f"Time: {events[0]['timestamp']} .. {events[-1]['timestamp']}")


if __name__ == "__main__":
    main()
