"""Drop the order_status table and its data (run by ./scripts/destroy.sh C7)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
from lh import Athena, safe  # noqa: E402

print(safe(Athena().run, "DROP TABLE IF EXISTS riverbend_lakehouse.order_status")[1] or "dropped riverbend_lakehouse.order_status")
