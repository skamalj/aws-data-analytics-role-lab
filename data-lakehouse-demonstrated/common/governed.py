"""Helpers shared by the governed challenges (C5, C6)."""
import boto3

from lh import Athena, base, safe, session


def revoke_iam_allowed_principals(database):
    """Turn off 'Use only IAM access control' for the database and its tables, so Lake Formation grants are enforced."""
    b = base()
    lf = boto3.client("lakeformation", region_name=b["region"])
    glue = boto3.client("glue", region_name=b["region"])
    p = {"DataLakePrincipalIdentifier": "IAM_ALLOWED_PRINCIPALS"}
    targets = [{"Database": {"Name": database}}] + [
        {"Table": {"DatabaseName": database, "Name": t["Name"]}} for t in glue.get_tables(DatabaseName=database)["TableList"]]
    for res in targets:
        _, err = safe(lf.revoke_permissions, Principal=p, Resource=res, Permissions=["ALL"])
        print(f"  revoke IAM_ALLOWED_PRINCIPALS on {list(res.values())[0].get('Name')}: {'ok' if not err else 'not granted'}")


def as_persona(role_arn):
    return Athena(sess=session(role_arn))


def probe(persona, athena, sql):
    """Run sql as a persona; return (rows, error)."""
    rows, err = safe(athena.rows, sql)
    short = (err or "").split(":", 1)[-1].strip()[:140]
    print(f"  [{persona:<15}] {sql[:80]:<80} -> " + (f"{len(rows)} rows, columns {list(rows[0]) if rows else []}" if rows is not None else f"DENIED/ERROR {short}"))
    return rows, err
