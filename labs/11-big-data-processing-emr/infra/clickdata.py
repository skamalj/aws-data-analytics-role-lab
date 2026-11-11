"""
Deterministic clickstream for Lab 11: 14 days (2024-06-01 .. 2024-06-14) of web/mobile
events WITHOUT a session id. The tracker lost it; sessions must be rebuilt.

Also contains `ground_truth()`, a plain-Python implementation of the sessionization
rule, used to produce the check values in the solution folder.
"""
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone

START = datetime(2024, 6, 1, tzinfo=timezone.utc)
DAYS = 14
SESSIONS_PER_DAY = 1500
GAP_S = 30 * 60
DEVICES = ["ios", "android", "desktop"]
CONVERT = {"ios": 0.30, "android": 0.22, "desktop": 0.38}   # P(checkout | cart) by device


def events():
    r = random.Random(1111)
    out = []
    for d in range(DAYS):
        day = START + timedelta(days=d)
        for _ in range(SESSIONS_PER_DAY):
            cust = f"C{r.randint(1, 500):05d}"
            dev = r.choices(DEVICES, [40, 35, 25])[0]
            ts = day + timedelta(seconds=r.randint(0, 86399))
            n = r.randint(1, 15)
            carted = False
            for i in range(n):
                if i == 0:
                    et = "page_view"
                else:
                    et = r.choices(["page_view", "search", "add_to_cart"], [70, 15, 15])[0]
                carted = carted or et == "add_to_cart"
                out.append((ts, cust, dev, et, f"P{r.randint(101, 118)}"))
                ts += timedelta(seconds=min(int(r.expovariate(1 / 90)) + 5, 20 * 60))
            if carted and r.random() < CONVERT[dev]:
                out.append((ts, cust, dev, "checkout", None))
    out.sort()
    return [{"event_ts": t.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "customer_id": c, "device": dv,
             "event_type": et, "product_id": p} for t, c, dv, et, p in out]


def ground_truth(evts):
    by_key = defaultdict(list)
    for e in evts:
        by_key[(e["customer_id"], e["device"])].append(e)
    sessions = []
    for (cust, dev), es in by_key.items():
        es.sort(key=lambda e: e["event_ts"])
        cur = None
        prev = None
        for e in es:
            t = datetime.strptime(e["event_ts"], "%Y-%m-%dT%H:%M:%S.000Z")
            if prev is None or (t - prev).total_seconds() > GAP_S:
                cur = {"customer_id": cust, "device": dev, "start": t, "end": t, "events": 0, "checkouts": 0, "carts": 0}
                sessions.append(cur)
            cur["end"] = t
            cur["events"] += 1
            cur["checkouts"] += e["event_type"] == "checkout"
            cur["carts"] += e["event_type"] == "add_to_cart"
            prev = t
    return sessions
