"""
Small boto3 helpers shared by the lab seed scripts and the deploy/destroy scripts.

CLI:
    python3 common/awslab.py outputs <stack>        # print stack outputs as KEY=VALUE
    python3 common/awslab.py empty-buckets <stack>  # delete every object/version in the stack's buckets
"""
import sys

import boto3


def session():
    return boto3.session.Session()


def outputs(stack):
    cfn = session().client("cloudformation")
    st = cfn.describe_stacks(StackName=stack)["Stacks"][0]
    return {o["OutputKey"]: o["OutputValue"] for o in st.get("Outputs", [])}


def put(bucket, key, body, content_type="text/plain"):
    if isinstance(body, str):
        body = body.encode()
    session().client("s3").put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
    print(f"  uploaded s3://{bucket}/{key} ({len(body):,} bytes)")


def empty_bucket(bucket):
    s3 = session().resource("s3")
    b = s3.Bucket(bucket)
    try:
        b.object_versions.delete()
        b.objects.all().delete()
        print(f"  emptied s3://{bucket}")
    except s3.meta.client.exceptions.NoSuchBucket:
        pass


def stack_buckets(stack):
    cfn = session().client("cloudformation")
    pages = cfn.get_paginator("list_stack_resources").paginate(StackName=stack)
    return [r["PhysicalResourceId"] for p in pages for r in p["StackResourceSummaries"]
            if r["ResourceType"] == "AWS::S3::Bucket" and r.get("PhysicalResourceId")
            and r["ResourceStatus"] != "DELETE_COMPLETE"]


if __name__ == "__main__":
    cmd, stack = sys.argv[1], sys.argv[2]
    if cmd == "outputs":
        for k, v in outputs(stack).items():
            print(f"{k}={v}")
    elif cmd == "empty-buckets":
        for bkt in stack_buckets(stack):
            empty_bucket(bkt)
    else:
        sys.exit(f"unknown command {cmd}")
