# Challenge S6: Nobody noticed

**Exam objective:** *Detect identity security events by using AWS CloudTrail and Amazon CloudWatch*
**Services:** AWS CloudTrail (trails, advanced event selectors, CloudWatch Logs delivery), Amazon CloudWatch (Logs metric filters, alarms), Amazon SNS, AgentCore Identity, AWS IAM, Amazon S3
**Time:** 30–40 minutes (plus ~15 minutes of CloudTrail delivery delay)  |  **Deploy:** `./scripts/deploy.sh S6`

## Situation

Last month, someone re-tagged a workload identity to get past the ABAC policy (see S1). Then they spent an afternoon trying to mint
tokens for agents they didn't own. Nobody noticed. The security team has since built an audit pipeline for agent identities:

```
CloudTrail trail larchmont-s6-identity-audit ──► S3 (archive) + CloudWatch Logs /larchmont/cloudtrail/agent-identity
   ──► metric filters (namespace Larchmont/AgentIdentity) ──► alarms ──► SNS larchmont-s6-identity-alerts
```

It must detect:

| Detection | Events | Metric | Alarm |
|---|---|---|---|
| Denied token operations | AgentCore Identity calls (`bedrock-agentcore.amazonaws.com`) that fail with an access-denied error | `TokenAccessDenied` | `larchmont-s6-token-access-denied` |
| Workload identity tampering | `TagResource`, `UntagResource`, `UpdateWorkloadIdentity` and `DeleteWorkloadIdentity` on AgentCore | `WorkloadIdentityTampering` | `larchmont-s6-workload-identity-tampering` |

The trail must record **token operations** on workload identities (`GetWorkloadAccessToken*`) as well as the management activity.

The incident drill (`simulate_incident.py`) has never raised an alarm.

Everything is in [`terraform/main.tf`](terraform/main.tf).

## Run and check

```bash
python3 missions/S6-identity-audit-detection/scenarios/simulate_incident.py    # a rogue operator + a re-tag of the canary identity
# wait ~5-15 minutes for CloudTrail -> CloudWatch Logs
python3 missions/S6-identity-audit-detection/scenarios/check.py
aws cloudtrail get-trail-status --name larchmont-s6-identity-audit          # LatestCloudWatchLogsDeliveryError
aws cloudtrail get-event-selectors --trail-name larchmont-s6-identity-audit
aws logs test-metric-filter --filter-pattern '<pattern>' --log-event-messages '<a CloudTrail record as JSON>'
```

`check.py` tests the filters against sample CloudTrail records right away. Its last three checks need a drill run after your fixes.

## Done when

`check.py` reports 13/13:
- the trail delivers to CloudWatch Logs and records write activity and token operations;
- both filters match what they must (and nothing else), and both alarms watch real filter metrics;
- the drill shows up as events and metric datapoints.

<details><summary>Hint 1</summary><code>get-trail-status</code> shows CloudWatch Logs delivery errors. What does CloudTrail need to do in the log group?</details>
<details><summary>Hint 2</summary>Is <code>TagResource</code> a read or a write? And are token operations on a workload identity management events or data events?</details>
<details><summary>Hint 3</summary>Every link in the chain has to match the next one exactly: event source, then filter, then metric name, then alarm.</details>
