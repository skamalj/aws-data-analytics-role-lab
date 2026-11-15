"""S5 check: the reporting agent verifies callers by JWT, records the filer from the verified token, and the legacy paths are closed."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
sys.path.insert(0, HERE)
from file_report import file  # noqa: E402
from sai import check, finish, mission  # noqa: E402

o = mission(os.path.join(HERE, ".."))
compliance_id = o["clients"]["compliance_portal"]["id"]

st, body = file("compliance", acting_as="cfo")
check("the Compliance Portal gets a reports.submit token and files a report", st == 200 and isinstance(body, dict) and body.get("filed") is True,
      f"status {st}: {body}")
body = body if isinstance(body, dict) else {}
check("the filer is taken from the verified token, not the payload", body.get("identity_source") == "jwt", f"identity_source: {body.get('identity_source')}")
check("a spoofed 'acting_as: cfo' is ignored - filed_by is the portal's client_id", body.get("filed_by") == compliance_id,
      f"filed_by: {body.get('filed_by')}")

st, body = file("advisor")
check("an Advisor Portal token (no reports.submit) is rejected", st in (401, 403), f"status {st}: {body}")
st, body = file("forged")
check("an unsigned, forged token is rejected", st in (401, 403), f"status {st}: {body}")
st, body = file("legacy-batch", acting_as="officer-17")
check("the legacy SigV4 batch path is closed", st != 200, f"status {st}: {body}")
finish()
