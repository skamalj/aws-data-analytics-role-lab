"""Helpers for talking to the lab's Aurora PostgreSQL database through the RDS Data API."""
import os
import sys
import time

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "common"))
from awslab import outputs  # noqa: E402

COLS = ["order_id", "order_ts", "customer_id", "product_id", "quantity", "unit_price",
        "discount", "total_amount", "channel", "store_id", "region", "status", "updated_at"]
TYPES = {"order_ts": "TIMESTAMP", "updated_at": "TIMESTAMP", "unit_price": "DECIMAL",
         "discount": "DECIMAL", "total_amount": "DECIMAL"}


class SourceDb:
    def __init__(self, stack):
        out = outputs(stack)
        self.kw = {"resourceArn": out["ClusterArn"], "secretArn": out["DbSecretArn"], "database": out["Database"]}
        self.client = boto3.client("rds-data")

    def sql(self, statement, retries=10):
        for i in range(retries):
            try:
                return self.client.execute_statement(sql=statement, **self.kw)
            except self.client.exceptions.DatabaseResumingException:
                print("  database is resuming, waiting...")
                time.sleep(15)
            except self.client.exceptions.BadRequestException as e:
                if "Communications link failure" in str(e) and i < retries - 1:
                    time.sleep(15)
                    continue
                raise
        raise RuntimeError("database did not become available")

    def insert_orders(self, rows, batch=500, upsert=False):
        ph = ", ".join(f":{c}" for c in COLS)
        stmt = f"INSERT INTO sales.orders ({', '.join(COLS)}) VALUES ({ph})"
        if upsert:
            stmt += (" ON CONFLICT (order_id) DO UPDATE SET status = EXCLUDED.status,"
                     " updated_at = EXCLUDED.updated_at")
        self.sql("SELECT 1")  # wake the database up
        for i in range(0, len(rows), batch):
            params = []
            for r in rows[i:i + batch]:
                p = []
                for c in COLS:
                    v = {"stringValue": str(r[c])} if c not in ("quantity",) else {"longValue": int(r[c])}
                    entry = {"name": c, "value": v}
                    if c in TYPES:
                        entry["typeHint"] = TYPES[c]
                    p.append(entry)
                params.append(p)
            self.client.batch_execute_statement(sql=stmt, parameterSets=params, **self.kw)
        print(f"  wrote {len(rows)} rows to sales.orders")
