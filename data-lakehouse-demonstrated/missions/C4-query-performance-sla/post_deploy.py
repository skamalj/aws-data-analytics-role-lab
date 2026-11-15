"""Load 20M sales rows with the legacy loader (run by ./scripts/deploy.sh C4; ~5 minutes, once)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
from lh import Athena, base, mission, run_glue  # noqa: E402

n = Athena().rows("SELECT count(*) AS n FROM riverbend_lakehouse.sales")[0]["n"]
if n == "0":
    run_glue(mission(HERE)["load_job"], {"--database": base()["database"], "--table": "sales"})
else:
    print(f"  sales already loaded ({n} rows)")
