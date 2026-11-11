"""
Deterministic synthetic data generator shared by every lab.

The fictional company is "Riverbend Outfitters", an outdoor-gear retailer with
physical stores and an online shop in four regions. Every lab uses the same
customers / products / orders so that results are comparable across labs.

Usage as a library:
    from datagen import customers, products, orders, to_csv, to_jsonl
Usage from the CLI (handy for inspecting data locally):
    python3 datagen.py orders --rows 20
"""
import csv
import io
import json
import random
import sys
from datetime import datetime, timedelta, timezone

SEED = 20240101

REGIONS = {
    "NA": ["Seattle", "Denver", "Toronto", "Austin", "Chicago"],
    "EU": ["Berlin", "Lyon", "Dublin", "Madrid", "Oslo"],
    "APAC": ["Sydney", "Pune", "Singapore", "Osaka", "Auckland"],
    "LATAM": ["Bogota", "Lima", "Santiago", "Monterrey", "Curitiba"],
}
COUNTRY = {
    "Seattle": "US", "Denver": "US", "Toronto": "CA", "Austin": "US", "Chicago": "US",
    "Berlin": "DE", "Lyon": "FR", "Dublin": "IE", "Madrid": "ES", "Oslo": "NO",
    "Sydney": "AU", "Pune": "IN", "Singapore": "SG", "Osaka": "JP", "Auckland": "NZ",
    "Bogota": "CO", "Lima": "PE", "Santiago": "CL", "Monterrey": "MX", "Curitiba": "BR",
}
FIRST = ["Ana", "Ben", "Chen", "Dara", "Eli", "Fatima", "Gus", "Hana", "Ivan", "Jo",
         "Kofi", "Lena", "Mateo", "Nia", "Omar", "Priya", "Quinn", "Rosa", "Sam", "Tariq"]
LAST = ["Alvarez", "Berg", "Costa", "Dubois", "Evans", "Fischer", "Gupta", "Hughes",
        "Ito", "Jensen", "Kim", "Lopez", "Moreau", "Nakamura", "Okafor", "Patel"]
CATEGORIES = {
    "Tents": [("Trailhead 2P Tent", 189.0), ("Summit 4P Tent", 349.0), ("Bivy Shelter", 129.0)],
    "Footwear": [("Ridge Hiking Boot", 159.0), ("Trail Runner", 119.0), ("Camp Sandal", 49.0)],
    "Apparel": [("Rain Shell Jacket", 139.0), ("Merino Base Layer", 79.0), ("Fleece Hoodie", 69.0)],
    "Packs": [("Daypack 22L", 89.0), ("Expedition Pack 65L", 259.0), ("Hydration Vest", 99.0)],
    "Cooking": [("Ultralight Stove", 59.0), ("Titanium Pot Set", 74.0), ("Water Filter", 44.0)],
    "Climbing": [("Harness", 64.0), ("Dynamic Rope 60m", 219.0), ("Chalk Bag", 19.0)],
}
CHANNELS = ["store", "web", "mobile"]
TIERS = ["bronze", "silver", "gold", "platinum"]
START = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _rng(offset=0):
    return random.Random(SEED + offset)


def products():
    out, pid = [], 100
    for cat, items in CATEGORIES.items():
        for name, price in items:
            pid += 1
            out.append({"product_id": f"P{pid}", "product_name": name,
                        "category": cat, "unit_price": price})
    return out


def customers(n=500):
    r = _rng(1)
    out = []
    for i in range(1, n + 1):
        region = r.choice(list(REGIONS))
        city = r.choice(REGIONS[region])
        fn, ln = r.choice(FIRST), r.choice(LAST)
        out.append({
            "customer_id": f"C{i:05d}",
            "first_name": fn,
            "last_name": ln,
            "email": f"{fn.lower()}.{ln.lower()}{i}@example.com",
            "phone": f"+1-555-{r.randint(100, 999)}-{r.randint(1000, 9999)}",
            "city": city,
            "country": COUNTRY[city],
            "region": region,
            "signup_date": (START - timedelta(days=r.randint(0, 900))).date().isoformat(),
            "loyalty_tier": r.choices(TIERS, weights=[50, 30, 15, 5])[0],
        })
    return out


def orders(n=5000, days=180, start=START, id_offset=0, seed_offset=2):
    """Orders spread over `days` days beginning at `start`."""
    r = _rng(seed_offset)
    custs = customers()
    prods = products()
    out = []
    for i in range(1, n + 1):
        c = r.choice(custs)
        p = r.choice(prods)
        qty = r.choices([1, 2, 3, 4], weights=[70, 20, 7, 3])[0]
        disc = r.choice([0, 0, 0, 0.05, 0.10, 0.15])
        ts = start + timedelta(seconds=r.randint(0, days * 86400 - 1))
        out.append({
            "order_id": f"O{id_offset + i:07d}",
            "order_ts": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "customer_id": c["customer_id"],
            "product_id": p["product_id"],
            "quantity": qty,
            "unit_price": p["unit_price"],
            "discount": disc,
            "total_amount": round(qty * p["unit_price"] * (1 - disc), 2),
            "channel": r.choices(CHANNELS, weights=[40, 45, 15])[0],
            "store_id": f"S{r.randint(1, 20):02d}",
            "region": c["region"],
            "status": r.choices(["COMPLETED", "RETURNED", "CANCELLED"], weights=[90, 7, 3])[0],
        })
    out.sort(key=lambda o: o["order_ts"])
    return out


def customer_profiles():
    """CRM profile documents (stored in DynamoDB in the federated-query lab)."""
    r = _rng(3)
    out = []
    for c in customers():
        pts = {"bronze": 200, "silver": 1500, "gold": 5000, "platinum": 15000}[c["loyalty_tier"]]
        out.append({
            "customer_id": c["customer_id"],
            "full_name": f"{c['first_name']} {c['last_name']}",
            "email": c["email"],
            "region": c["region"],
            "loyalty_tier": c["loyalty_tier"],
            "loyalty_points": pts + r.randint(0, pts),
            "marketing_opt_in": r.random() < 0.6,
            "preferred_channel": r.choice(["email", "sms", "push"]),
            "last_login": (START + timedelta(days=r.randint(0, 180))).date().isoformat(),
        })
    return out


def clickstream_event(r):
    """One random web/mobile event (used by streaming producers)."""
    c = f"C{r.randint(1, 500):05d}"
    etype = r.choices(["page_view", "add_to_cart", "checkout", "search"],
                      weights=[70, 15, 5, 10])[0]
    return {
        "event_id": f"{r.getrandbits(64):016x}",
        "event_ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "event_type": etype,
        "customer_id": c,
        "session_id": f"sess-{r.randint(1, 2000)}",
        "product_id": r.choice(products())["product_id"],
        "device": r.choice(["ios", "android", "desktop"]),
        "region": r.choice(list(REGIONS)),
    }


def sensor_reading(r, device_count=10, anomaly_rate=0.03):
    """Cold-storage warehouse freezer telemetry (used by real-time lab)."""
    dev = f"freezer-{r.randint(1, device_count):02d}"
    temp = r.gauss(-18.0, 1.2)
    if r.random() < anomaly_rate:
        temp = r.uniform(-8.0, 2.0)  # door left open / compressor failure
    return {
        "device_id": dev,
        "warehouse": f"WH-{int(dev[-2:]) % 3 + 1}",
        "reading_ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "temperature_c": round(temp, 2),
        "humidity_pct": round(r.uniform(30, 60), 1),
        "door_open": temp > -10 and r.random() < 0.7,
    }


def to_csv(rows, delimiter=",", header=True):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), delimiter=delimiter, lineterminator="\n")
    if header:
        w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def to_jsonl(rows):
    return "".join(json.dumps(x) + "\n" for x in rows)


if __name__ == "__main__":
    kind = sys.argv[1] if len(sys.argv) > 1 else "orders"
    rows = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    data = {"orders": lambda: orders(rows), "customers": lambda: customers(rows),
            "products": products}[kind]()
    sys.stdout.write(to_csv(data[:rows]))
