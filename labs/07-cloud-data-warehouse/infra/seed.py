"""Stage 2024 sales (gzip CSV, split into 4 files for parallel COPY) and the 2023 archive."""
import argparse
import gzip
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "common"))
from awslab import outputs, put  # noqa: E402
from datagen import customers, orders, products, to_csv  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--stack", required=True)
b = outputs(ap.parse_args().stack)["StagingBucket"]

o = orders(n=200_000, days=366)
for i in range(4):
    put(b, f"stage/orders/orders_2024_part{i}.csv.gz", gzip.compress(to_csv(o[i::4]).encode()), "application/gzip")
put(b, "stage/customers/customers.csv", to_csv(customers()), "text/csv")
put(b, "stage/products/products.csv", to_csv(products()), "text/csv")

archive = orders(n=50_000, days=365, start=datetime(2023, 1, 1, tzinfo=timezone.utc),
                 id_offset=900_000, seed_offset=21)
put(b, "archive/orders_2023/orders_2023.csv", to_csv(archive), "text/csv")
