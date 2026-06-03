import sqlite3
import json

conn = sqlite3.connect('data/store_intel.db')
cursor = conn.cursor()

print("Events Count:", cursor.execute("SELECT COUNT(*) FROM events").fetchone()[0])
print("Event Types:", cursor.execute("SELECT event_type, COUNT(*) FROM events GROUP BY event_type").fetchall())
print("Unique Visitors:", len(cursor.execute("SELECT DISTINCT visitor_id FROM events").fetchall()))

entries = [r[0] for r in cursor.execute("SELECT DISTINCT visitor_id FROM events WHERE event_type='ENTRY'").fetchall()]
print(f"Visitors with ENTRY ({len(entries)}):", entries)

billing = [r[0] for r in cursor.execute("SELECT DISTINCT visitor_id FROM events WHERE event_type='BILLING_QUEUE_JOIN' OR zone_id='BILLING'").fetchall()]
print(f"Visitors with BILLING/QUEUE ({len(billing)}):", billing)

# Let's see some details on matches
print("\nPOS Transactions:")
for r in cursor.execute("SELECT transaction_id, timestamp, basket_value_inr FROM pos_transactions").fetchall():
    print("  ", r)

conn.close()
