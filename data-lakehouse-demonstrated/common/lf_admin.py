"""
Lake Formation data lake administrator for the governed challenges (C5, C6).

    python3 common/lf_admin.py add        back up the current Data Lake settings (once) and add the caller as admin
    python3 common/lf_admin.py restore    restore the backup, unless another governed challenge is still deployed

Terraform must run as a data lake administrator to create LF-Tags, data cell filters and grants.
"""
import glob
import json
import os
import re
import sys

import boto3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP = os.path.expanduser("~/.riverbend-lh-lakeformation-settings-backup.json")
GOVERNED = ["C5", "C6"]


def caller_principal_arn():
    arn = boto3.client("sts").get_caller_identity()["Arn"]
    m = re.match(r"arn:aws:sts::(\d+):assumed-role/([^/]+)/.+", arn)   # session ARN -> role ARN
    return f"arn:aws:iam::{m.group(1)}:role/{m.group(2)}" if m else arn


def lf():
    return boto3.client("lakeformation", region_name=os.environ.get("AWS_REGION") or _base_region())


def _base_region():
    try:
        st = json.load(open(os.path.join(ROOT, "base", "terraform", "terraform.tfstate")))
        return st["outputs"]["region"]["value"]
    except Exception:  # noqa: BLE001
        return None


def deployed(cid):
    for st in glob.glob(os.path.join(ROOT, "missions", f"{cid}-*", "terraform", "terraform.tfstate")):
        if json.load(open(st)).get("resources"):
            return True
    return False


def add():
    c = lf()
    settings = c.get_data_lake_settings()["DataLakeSettings"]
    if not os.path.exists(BACKUP):
        json.dump(settings, open(BACKUP, "w"), indent=2, default=str)
        print(f"backed up Lake Formation settings to {BACKUP}")
    me = caller_principal_arn()
    admins = settings.get("DataLakeAdmins", [])
    if not any(a["DataLakePrincipalIdentifier"] == me for a in admins):
        settings["DataLakeAdmins"] = admins + [{"DataLakePrincipalIdentifier": me}]
        c.put_data_lake_settings(DataLakeSettings=settings)
    print(f"data lake administrator: {me}")


def restore(current=None):
    others = [g for g in GOVERNED if g != current and deployed(g)]
    if others:
        print(f"leaving Lake Formation admin in place: {', '.join(others)} still deployed")
        return
    if not os.path.exists(BACKUP):
        print("no Lake Formation settings backup; nothing to restore")
        return
    lf().put_data_lake_settings(DataLakeSettings=json.load(open(BACKUP)))
    os.remove(BACKUP)
    print("restored the original Lake Formation settings")


if __name__ == "__main__":
    if sys.argv[1] == "add":
        add()
    else:
        restore(sys.argv[2] if len(sys.argv) > 2 else None)
