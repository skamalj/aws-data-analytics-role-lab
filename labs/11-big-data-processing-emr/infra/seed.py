"""Upload 14 days of clickstream as gzip JSON Lines, Hive-partitioned by event date."""
import argparse
import gzip
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "common"))
from awslab import outputs, put  # noqa: E402
from clickdata import events  # noqa: E402
from datagen import to_jsonl  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--stack", required=True)
b = outputs(ap.parse_args().stack)["DataBucket"]
by_day = defaultdict(list)
for e in events():
    by_day[e["event_ts"][:10]].append(e)
for day, rows in sorted(by_day.items()):
    for part in range(2):
        put(b, f"clickstream/dt={day}/events-{part:03d}.json.gz",
            gzip.compress(to_jsonl(rows[part::2]).encode()), "application/gzip")
