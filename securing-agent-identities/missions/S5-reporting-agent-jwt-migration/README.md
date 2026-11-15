# Challenge S5: Anyone can file as anyone

**Exam objective:** *Migrate the regulatory reporting agent to JWT-based identity verification*
**Services:** Amazon Bedrock AgentCore Runtime (custom JWT authorizer, request header allowlist), Amazon Cognito, AWS IAM
**Time:** 30–40 minutes  |  **Deploy:** `./scripts/deploy.sh S5`

## Situation

The regulatory reporting agent (`larchmont_s5_regulatory_reporting`) files reports with the regulator in Larchmont's name. Every report
records **who filed it**. Today the agent:
- accepts any caller with IAM permission to invoke it (SigV4), such as the nightly `larchmont-s5-legacy-batch` job;
- takes the filer's name from the request body (`"acting_as": "officer-17"`).

Internal audit showed that a caller can file a report as `"acting_as": "cfo"` and the record says the CFO filed it.

The migration plan (approved, half finished):
1. **Inbound:** the runtime verifies a JWT from the workforce pool. Only the **Compliance Portal** client with scope
   **`larchmont/reports.submit`** may call. All other tokens, unsigned tokens and SigV4 callers are rejected.
2. **Identity:** the agent records the filer from the **verified token** (`client_id`) and ignores anything the body claims.
   The agent supports this (`IDENTITY_MODE = jwt`), provided the runtime passes the verified token through to it.
3. **Callers:** the Compliance Portal (`larchmont-s5-compliance-portal`) obtains `reports.submit` tokens. The legacy batch job is retired.

Everything is in [`terraform/main.tf`](terraform/main.tf). The agent's identity logic is `caller()` in [`common/agent/agent.py`](../../common/agent/agent.py).

## Run and check

```bash
python3 missions/S5-reporting-agent-jwt-migration/scenarios/file_report.py --as compliance --acting-as cfo
python3 missions/S5-reporting-agent-jwt-migration/scenarios/file_report.py --as legacy-batch --acting-as officer-17
python3 missions/S5-reporting-agent-jwt-migration/scenarios/file_report.py --as advisor        # or --as forged
python3 missions/S5-reporting-agent-jwt-migration/scenarios/check.py
```

## Done when

`check.py` reports 6/6:
- the Compliance Portal files, and the record shows the portal's verified `client_id` even when the body claims `cfo`;
- advisor tokens, forged tokens and the legacy SigV4 job are all rejected.

<details><summary>Hint 1</summary>Work through the plan in order. For step 3, the Compliance Portal can only get a token whose scope its app client allows.</details>
<details><summary>Hint 2</summary>After you add the authorizer, the agent still says <code>identity_source: payload</code>. What decides that?</details>
<details><summary>Hint 3</summary>With <code>IDENTITY_MODE = jwt</code> the agent sees no caller at all. By default, AgentCore Runtime doesn't forward the <code>Authorization</code> header to your code.</details>
