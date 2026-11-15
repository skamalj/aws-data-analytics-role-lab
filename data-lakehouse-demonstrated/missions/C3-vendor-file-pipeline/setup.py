"""Create the Iceberg table riverbend_lakehouse.vendor_shipments (run by ./scripts/deploy.sh C3)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
from lh import Athena, base  # noqa: E402

Athena().run_file(os.path.join(HERE, "sql", "create_vendor_shipments.sql"), {"LAKE_BUCKET": base()["lake_bucket"]})
