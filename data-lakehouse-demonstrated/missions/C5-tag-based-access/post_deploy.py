"""Stop IAM-only access on the governed database so Lake Formation permissions are enforced (run by deploy.sh C5)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
from governed import revoke_iam_allowed_principals  # noqa: E402

revoke_iam_allowed_principals("riverbend_governed_c5")
