"""
Add the current caller as a Lake Formation data lake administrator (backing up the
existing settings first), or restore the backup.

    python3 lf_admin.py add
    python3 lf_admin.py restore
"""
import json
import os
import re
import sys

import boto3

BACKUP = os.path.expanduser("~/.cq-da-06-lakeformation-settings-backup.json")
lf = boto3.client("lakeformation")


def caller_principal_arn():
    arn = boto3.client("sts").get_caller_identity()["Arn"]
    # An assumed-role session ARN must be converted to its IAM role ARN.
    m = re.match(r"arn:aws:sts::(\d+):assumed-role/([^/]+)/.+", arn)
    return f"arn:aws:iam::{m.group(1)}:role/{m.group(2)}" if m else arn


def add():
    settings = lf.get_data_lake_settings()["DataLakeSettings"]
    if not os.path.exists(BACKUP):
        with open(BACKUP, "w") as f:
            json.dump(settings, f, indent=2, default=str)
        print(f"backed up current settings to {BACKUP}")
    me = caller_principal_arn()
    admins = settings.get("DataLakeAdmins", [])
    if not any(a["DataLakePrincipalIdentifier"] == me for a in admins):
        admins.append({"DataLakePrincipalIdentifier": me})
        settings["DataLakeAdmins"] = admins
        lf.put_data_lake_settings(DataLakeSettings=settings)
    print(f"data lake admin: {me}")


def restore():
    if not os.path.exists(BACKUP):
        sys.exit("no backup found; nothing to restore")
    with open(BACKUP) as f:
        settings = json.load(f)
    lf.put_data_lake_settings(DataLakeSettings=settings)
    os.remove(BACKUP)
    print("restored original Lake Formation settings")


if __name__ == "__main__":
    {"add": add, "restore": restore}[sys.argv[1]]()
