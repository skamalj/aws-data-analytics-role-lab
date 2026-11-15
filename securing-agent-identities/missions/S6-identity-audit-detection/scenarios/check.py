"""S6 check: CloudTrail records AgentCore identity activity into CloudWatch Logs, and the filters and alarms detect the incident."""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from sai import base, check, finish, mission, session  # noqa: E402

b, o = base(), mission(os.path.join(HERE, ".."))
s = session()
ct, logs, cw = s.client("cloudtrail"), s.client("logs"), s.client("cloudwatch")

# ---------------------------------------------------------------- trail
st = ct.get_trail_status(Name=o["trail_name"])
check("the trail is logging", st.get("IsLogging"), "")
trail = ct.get_trail(Name=o["trail_name"])["Trail"]
check("the trail delivers to the CloudWatch Logs group", o["log_group"] in trail.get("CloudWatchLogsLogGroupArn", ""), trail.get("CloudWatchLogsLogGroupArn", "none"))
sim = s.client("iam").simulate_principal_policy(
    PolicySourceArn=o["delivery_role_arn"], ActionNames=["logs:CreateLogStream", "logs:PutLogEvents"],
    ResourceArns=[f"arn:aws:logs:{b['region']}:{b['account_id']}:log-group:{o['log_group']}:log-stream:x"])
dec = {r["EvalActionName"]: r["EvalDecision"] for r in sim["EvaluationResults"]}
check("the delivery role can create log streams and put log events", all(v == "allowed" for v in dec.values()), f"{dec}")

sel = ct.get_event_selectors(TrailName=o["trail_name"]).get("AdvancedEventSelectors", [])


def fields(x):
    return {f["Field"]: f for f in x["FieldSelectors"]}


mgmt = [fields(x) for x in sel if fields(x).get("eventCategory", {}).get("Equals") == ["Management"]]
check("write management events are recorded (TagResource, UpdateWorkloadIdentity, DeleteWorkloadIdentity, denied calls)",
      any(f.get("readOnly", {}).get("Equals") != ["true"] for f in mgmt), f"management selectors: {mgmt}")
data = [fields(x) for x in sel if fields(x).get("eventCategory", {}).get("Equals") == ["Data"]]
agentcore_data = [f for f in data if any(v.startswith("AWS::BedrockAgentCore::") for v in
                                         f.get("resources.type", {}).get("Equals", []) + f.get("resources.type", {}).get("StartsWith", []))]
check("AgentCore Identity data events (token operations) are recorded", bool(agentcore_data), f"data selectors: {data}")

# ---------------------------------------------------------------- filters (tested against sample CloudTrail records)
mf = {m["filterName"]: m for m in logs.describe_metric_filters(logGroupName=o["log_group"])["metricFilters"]}
denied = {"eventSource": "bedrock-agentcore.amazonaws.com", "eventName": "GetWorkloadAccessToken", "errorCode": "AccessDenied",
          "errorMessage": "User is not authorized to perform: bedrock-agentcore:GetWorkloadAccessToken"}
denied_exc = {**denied, "errorCode": "AccessDeniedException"}
ok_call = {"eventSource": "bedrock-agentcore.amazonaws.com", "eventName": "GetWorkloadAccessToken"}
tag = {"eventSource": "bedrock-agentcore.amazonaws.com", "eventName": "TagResource", "requestParameters": {"tags": {"team": "trading"}}}
other_svc = {"eventSource": "bedrock.amazonaws.com", "eventName": "InvokeModel", "errorCode": "AccessDenied"}


def matches(name, event):
    pat = mf.get(name, {}).get("filterPattern", "")
    return bool(pat) and bool(logs.test_metric_filter(filterPattern=pat, logEventMessages=[json.dumps(event)])["matches"])


f1, f2 = o["filters"]["token_denied"], o["filters"]["tampering"]
check("the token-denial filter matches denied AgentCore token calls (AccessDenied and AccessDeniedException)",
      matches(f1, denied) and matches(f1, denied_exc), mf.get(f1, {}).get("filterPattern", "missing"))
check("the token-denial filter ignores successful calls and other services", not matches(f1, ok_call) and not matches(f1, other_svc), "")
check("the tampering filter matches TagResource on AgentCore", matches(f2, tag), mf.get(f2, {}).get("filterPattern", "missing"))

# ---------------------------------------------------------------- alarms wired to filter metrics
emitted = {(t["metricNamespace"], t["metricName"]) for m in mf.values() for t in m["metricTransformations"]}
for a in cw.describe_alarms(AlarmNames=o["alarms"])["MetricAlarms"]:
    wired = (a["Namespace"], a["MetricName"]) in emitted
    check(f"alarm {a['AlarmName']} watches a metric a filter emits, and notifies SNS",
          wired and o["topic_arn"] in a.get("AlarmActions", []), f"{a['Namespace']}/{a['MetricName']} emitted={wired}")

# ---------------------------------------------------------------- live: did the simulated incident get detected?
since = int((time.time() - 3 * 3600) * 1000)
ev = logs.filter_log_events(logGroupName=o["log_group"], startTime=since,
                            filterPattern='{ $.eventSource = "bedrock-agentcore.amazonaws.com" }', limit=50).get("events", [])
names = sorted({json.loads(e["message"]).get("eventName") for e in ev})
check("AgentCore identity events from the last 3 hours are in CloudWatch Logs (run simulate_incident.py, wait ~15 min)", bool(ev), f"event names: {names}")
for name in ("TokenAccessDenied", "WorkloadIdentityTampering"):
    pts = cw.get_metric_statistics(Namespace=o["namespace"], MetricName=name, StartTime=time.time() - 3 * 3600, EndTime=time.time(),
                                   Period=300, Statistics=["Sum"]).get("Datapoints", [])
    check(f"metric {name} recorded the simulated incident", sum(p["Sum"] for p in pts) >= 1, f"{len(pts)} datapoints")
finish()
