"""
Scenario driver: the content team uploads the document set, then publishes a SHORTER revision of
the returns policy a minute later (as happens every season).

    python3 missions/D9-diy-ingestion-pipeline/scenarios/upload_docs.py
"""
import glob
import os
import sys
import time

import boto3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from checks import mission_outputs  # noqa: E402

out = mission_outputs(os.path.join(HERE, ".."))
s3 = boto3.client("s3", region_name=out["region"])
for path in sorted(glob.glob(os.path.join(HERE, "..", "docs", "*.md"))):
    key = f"library/{os.path.basename(path)}"
    s3.upload_file(path, out["docs_bucket"], key)
    print(f"  uploaded {key}")
print("  waiting 60 s, then publishing a shorter revision of returns-policy.md ...")
time.sleep(60)
text = open(os.path.join(HERE, "..", "docs", "returns-policy.md")).read()
revision = text.split("## Refund timing")[0] + "\n## Revision note\n\nThis policy was shortened for the new season.\n"
s3.put_object(Bucket=out["docs_bucket"], Key="library/returns-policy.md", Body=revision.encode())
print("  uploaded library/returns-policy.md (revision)")
print("done - give the pipeline ~1 minute, then run scenarios/check.py")
