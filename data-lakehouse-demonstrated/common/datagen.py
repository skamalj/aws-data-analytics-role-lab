"""Deterministic retail data for the Riverbend lakehouse challenges."""
import random
from datetime import datetime, timedelta

PRODUCTS = [("P101", "Trailhead 2P Tent", "Tents", 189.0), ("P102", "Summit 4P Tent", "Tents", 349.0),
            ("P103", "Bivy Shelter", "Tents", 129.0), ("P104", "Ridge Hiking Boot", "Footwear", 159.0),
            ("P105", "Trail Runner", "Footwear", 119.0), ("P106", "Camp Sandal", "Footwear", 49.0),
            ("P107", "Rain Shell Jacket", "Apparel", 139.0), ("P108", "Merino Base Layer", "Apparel", 79.0),
            ("P109", "Fleece Hoodie", "Apparel", 69.0), ("P110", "Daypack 22L", "Packs", 89.0),
            ("P111", "Expedition Pack 65L", "Packs", 259.0), ("P112", "Hydration Vest", "Packs", 99.0),
            ("P113", "Ultralight Stove", "Cooking", 59.0), ("P114", "Titanium Pot Set", "Cooking", 74.0),
            ("P115", "Water Filter", "Cooking", 44.0), ("P116", "Harness", "Climbing", 64.0),
            ("P117", "Dynamic Rope 60m", "Climbing", 219.0), ("P118", "Chalk Bag", "Climbing", 19.0)]
REGIONS = ["NA", "EU", "APAC", "LATAM"]


def ts(day, r):
    return (datetime(2026, 3, day) + timedelta(seconds=r.randint(0, 86399))).strftime("%Y-%m-%d %H:%M:%S")


def order(oid, day, r, status="PLACED"):
    p = r.choice(PRODUCTS)
    q = r.choice([1, 1, 1, 2, 3])
    t = ts(day, r)
    return {"order_id": oid, "customer_id": f"C{r.randint(1, 500):05d}", "product_id": p[0], "quantity": q,
            "amount": round(q * p[3], 2), "region": r.choice(REGIONS), "status": status, "order_ts": t, "updated_at": t}


def order_deliveries():
    """Three daily order exports with the usual real-world mess (see challenge C1)."""
    r = random.Random(101)
    day1 = [order(f"O{1000 + i}", 1, r) for i in range(300)]
    day2 = [order(f"O{2000 + i}", 2, r) for i in range(200)]
    updates = []
    for o in day1[:100]:                                     # 100 day-1 orders ship on day 2
        u = dict(o, status="SHIPPED", updated_at=ts(2, r))
        updates.append(u)
    twice = []
    for o in day2[:20]:                                      # 20 day-2 orders are cancelled later the same day
        later = (datetime.strptime(o["updated_at"], "%Y-%m-%d %H:%M:%S") + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        twice.append(dict(o, status="CANCELLED", updated_at=later))
    resent = [dict(x) for x in day2[50:80]]                  # the export job re-sent 30 lines
    day2_file = day2 + updates + twice + resent
    r.shuffle(day2_file)
    day3 = [order(f"O{3000 + i}", 3, r) for i in range(100)]
    replay = [dict(o) for o in day1[:50]]                    # a replay of old day-1 versions (already SHIPPED!)
    day3_file = day3 + replay
    r.shuffle(day3_file)
    return {"2026-03-01": day1, "2026-03-02": day2_file, "2026-03-03": day3_file}


def expected_orders():
    latest = {}
    for day, rows in sorted(order_deliveries().items()):
        for o in rows:
            cur = latest.get(o["order_id"])
            if cur is None or o["updated_at"] > cur["updated_at"]:
                latest[o["order_id"]] = o
    return latest
