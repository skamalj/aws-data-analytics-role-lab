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


# ----------------------------------------------------------------- governed data (C5, C6)
FIRST = ["Ava", "Liam", "Maya", "Noah", "Zoe", "Omar", "Ines", "Kenji", "Lena", "Raj", "Sofia", "Tom"]
LAST = ["Garcia", "Chen", "Muller", "Okafor", "Silva", "Tanaka", "Novak", "Haddad", "Rossi", "Kim"]
SEGMENTS = ["outdoor-pro", "weekend", "family", "new"]


def _customer(i, r):
    f, l = r.choice(FIRST), r.choice(LAST)
    return {"customer_id": f"C{i:05d}", "name": f"{f} {l}", "email": f"{f.lower()}.{l.lower()}{i}@example.com",
            "phone": f"+1-555-{r.randint(1000, 9999)}", "region": REGIONS[i % 4], "segment": r.choice(SEGMENTS),
            "marketing_opt_in": "true" if r.random() < 0.55 else "false", "credit_score": r.randint(520, 830),
            "lifetime_value": round(r.uniform(50, 6000), 2)}


def governed_c5():
    """Tables for C5 (tag-based access control). Returns {table: (columns, rows)}."""
    r = random.Random(505)
    cust = [_customer(i, r) for i in range(1, 401)]
    sessions = [{"session_id": f"W{i:06d}", "customer_id": f"C{r.randint(1, 400):05d}", "page": r.choice(["/", "/tents", "/boots", "/packs", "/sale"]),
                 "duration_s": r.randint(5, 900), "device": r.choice(["mobile", "desktop", "tablet"])} for i in range(1, 1001)]
    reviews = [{"review_id": f"R{i:05d}", "product_id": r.choice(PRODUCTS)[0], "rating": r.randint(1, 5),
                "review_text": r.choice(["love it", "too heavy", "great value", "runs small", "would buy again"])} for i in range(1, 301)]
    payroll = [{"employee_id": f"E{i:04d}", "name": f"{r.choice(FIRST)} {r.choice(LAST)}", "salary": r.randint(42000, 180000),
                "bank_account": f"GB{r.randint(10**9, 10**10 - 1)}"} for i in range(1, 41)]
    return {
        "customers": (["customer_id", "name", "email", "phone", "region", "segment", "lifetime_value"], cust),
        "web_sessions": (["session_id", "customer_id", "page", "duration_s", "device"], sessions),
        "product_reviews": (["review_id", "product_id", "rating", "review_text"], reviews),
        "payroll": (["employee_id", "name", "salary", "bank_account"], payroll),
    }


def governed_c6():
    """customer_profiles for C6 (data cell filters)."""
    r = random.Random(606)
    cols = ["customer_id", "name", "email", "region", "segment", "marketing_opt_in", "credit_score", "lifetime_value"]
    return cols, [_customer(i, r) for i in range(1, 601)]


def write_csv(path, cols, rows):
    with open(path, "w") as f:
        for row in rows:
            f.write(",".join(str(row[c]) for c in cols) + "\n")


# ----------------------------------------------------------------- order status stream (C7)
def order_status_waves():
    """Three waves of CDC-style events for Firehose -> Iceberg. Returns (waves, expected {order_id: (status, amount)})."""
    r = random.Random(707)
    ids = [f"O-7{i:04d}" for i in range(1, 201)]
    state, waves = {}, []

    def ev(oid, status, amount, op, seq):
        return {"order_id": oid, "status": status, "amount": amount, "updated_at": f"2026-03-10T{seq:02d}:00:00Z", "op": op}

    w1 = []
    for oid in ids:
        amt = float(r.choice(PRODUCTS)[3])
        state[oid] = ("PLACED", amt)
        w1.append(ev(oid, "PLACED", amt, "insert", 8))
    waves.append(w1)
    upd = ids[:120]
    w2 = []
    for oid in upd:
        st = r.choice(["PAID", "SHIPPED"])
        state[oid] = (st, state[oid][1])
        w2.append(ev(oid, st, state[oid][1], "update", 12))
    waves.append(w2)
    w3 = []
    for oid in upd[:60]:
        state[oid] = ("DELIVERED", state[oid][1])
        w3.append(ev(oid, "DELIVERED", state[oid][1], "update", 18))
    for oid in ids[180:]:                          # 20 test orders purged
        state.pop(oid)
        w3.append({"order_id": oid, "op": "delete"})
    waves.append(w3)
    return waves, state
