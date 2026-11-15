"""Create/load catalog.products (~200k rows, first run takes a minute) and apply db/indexes.sql (run by ./scripts/deploy.sh D8)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
from dbsql import Db  # noqa: E402

db = Db("admin")
print(">> catalog"); db.run_file(os.path.join(HERE, "db", "catalog.sql"), quiet=True)
print(">> indexes"); db.run_file(os.path.join(HERE, "db", "indexes.sql"))
