"""Apply db/schema.sql as the admin user (run by ./scripts/deploy.sh D6)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
from dbsql import Db  # noqa: E402

Db("admin").run_file(os.path.join(HERE, "db", "schema.sql"))
