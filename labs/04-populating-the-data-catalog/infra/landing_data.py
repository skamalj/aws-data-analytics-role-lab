"""Builds the deliberately messy landing-zone files for Lab 04 (shared by seed.py and add_month.py)."""
import gzip
import json
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "common"))
from datagen import orders, products, to_csv, to_jsonl  # noqa: E402

STORE_COLS = ["order_id", "order_ts", "store_id", "product_id", "quantity", "total_amount"]
RETURN_REASONS = ["wrong_size", "damaged", "not_as_described", "changed_mind"]


def web_orders_by_month(rows):
    out = defaultdict(list)
    for o in rows:
        if o["channel"] in ("web", "mobile"):
            out[(o["order_ts"][:4], o["order_ts"][5:7])].append(o)
    return out


def store_sales_files(rows):
    """Pipe-delimited, no header row."""
    out = defaultdict(list)
    for o in rows:
        if o["channel"] == "store":
            out[o["order_ts"][:7]].append("|".join(str(o[c]) for c in STORE_COLS))
    return {m: "\n".join(lines) + "\n" for m, lines in out.items()}


def returns_rows(rows):
    r = random.Random(7)
    res = []
    for o in rows:
        if o["status"] == "RETURNED":
            ts = datetime.strptime(o["order_ts"], "%Y-%m-%d %H:%M:%S") + timedelta(days=r.randint(2, 20))
            res.append({"order_id": o["order_id"], "return_ts": ts.strftime("%Y-%m-%d %H:%M:%S"),
                        "reason": r.choice(RETURN_REASONS), "refund_amount": o["total_amount"]})
    return res


def clickstream_day(day, n=2000):
    r = random.Random(int(day.strftime("%Y%m%d")))
    prods = products()
    rows = []
    for _ in range(n):
        ts = day + timedelta(seconds=r.randint(0, 86399))
        rows.append({
            "event_id": f"{r.getrandbits(64):016x}",
            "event_ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event_type": r.choices(["page_view", "add_to_cart", "checkout", "search"], [70, 15, 5, 10])[0],
            "customer_id": f"C{r.randint(1, 500):05d}",
            "product_id": r.choice(prods)["product_id"],
            "device": r.choice(["ios", "android", "desktop"]),
        })
    rows.sort(key=lambda x: x["event_ts"])
    return rows


def gz(text):
    return gzip.compress(text.encode())


def jsonl(rows):
    return to_jsonl(rows)


__all__ = ["orders", "to_csv", "jsonl", "gz", "web_orders_by_month", "store_sales_files",
           "returns_rows", "clickstream_day", "json", "datetime", "timezone", "timedelta"]
