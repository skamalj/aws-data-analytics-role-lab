"""Scenario driver: the supplier delivers product feed v2 and the merge job loads it."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
import datagen  # noqa: E402
from lh import base, mission, run_glue, session  # noqa: E402

b, m = base(), mission(os.path.join(HERE, ".."))
key = "suppliers/feed=v2/products.json"
session().client("s3").put_object(Bucket=b["raw_bucket"], Key=key,
                                  Body="".join(json.dumps(r) + "\n" for r in datagen.supplier_feed_v2()).encode())
print(f"  delivered s3://{b['raw_bucket']}/{key} (2,000 rows; new attribute 'brand'; prices with cents)")
run_glue(m["merge_job"], {"--source_path": f"s3://{b['raw_bucket']}/suppliers/feed=v2/", "--database": b["database"], "--table": "products"})
