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


def supplier_feed_v2():
    """Supplier feed v2: a new `brand` attribute and prices with cents (C2)."""
    r = random.Random(202)
    brands = ["Kestrel", "Northpine", "Talus", "Cairn", "Ember", "Glacier"]
    cats = ["Tents", "Footwear", "Apparel", "Packs", "Cooking", "Climbing"]
    rows = []
    for n in list(range(1, 60001, 60)) + list(range(60001, 61001)):      # 1,000 updates + 1,000 new SKUs
        rows.append({"product_id": f"SKU{n:06d}", "product_name": f"Supplier item {n}",
                     "category": cats[(n // 6) % 6], "price": round(19 + n % 480 + r.choice([0.49, 0.95, 0.99]), 2),
                     "stock": n % 250, "brand": r.choice(brands)})
    return rows


def vendor_files():
    """Three vendor shipment files for C3: two valid, one missing a required column."""
    r = random.Random(303)
    header = ["shipment_id", "vendor_id", "product_id", "quantity", "shipped_at"]

    def rows(lo, hi, vendor):
        return [[f"SH{n:05d}", vendor, r.choice(PRODUCTS)[0], str(r.randint(5, 200)), ts(r.randint(1, 28), r)] for n in range(lo, hi)]
    good1 = [header] + rows(1, 151, "V-NORTHPINE")
    good2 = [header] + rows(151, 301, "V-CAIRN")
    bad = [[h for h in header if h != "quantity"]] + [[c for i, c in enumerate(x) if i != 3] for x in rows(301, 351, "V-TALUS")]
    csv = lambda t: "\n".join(",".join(x) for x in t) + "\n"
    return {"northpine-2026-03-04.csv": csv(good1), "cairn-2026-03-04.csv": csv(good2), "talus-2026-03-04.csv": csv(bad)}
