# Challenge S3 solution: The advisor agent's front door

```bash
patch -p1 < solutions/S3-scoped-jwt-inbound/fix.patch
./scripts/deploy.sh S3
python3 missions/S3-scoped-jwt-inbound/scenarios/check.py
```

| # | Symptom | Fault | Fix |
|---|---|---|---|
| 1 | Every workforce token gets a 401 | `discovery_url` points at the **staging** pool. Wrong issuer and wrong signing keys, and staging tokens would be trusted | The workforce pool's `/.well-known/openid-configuration` |
| 2 | Still a 401 for every token | `allowed_audience = ["larchmont"]`. Cognito **access** tokens have no `aud` claim (ID tokens do). They carry `client_id` and `scope` | Remove `allowed_audience`. Restrict with `allowed_clients` |
| 3 | The analytics dashboard gets in | Its client id is in `allowed_clients` | `allowed_clients = [advisor portal]` |
| 4 | A `reports.read`-only token from the Advisor Portal gets in | No scope check: any token from an allowed client works, whatever it was issued for | `allowed_scopes = ["larchmont/advisor.invoke"]` |

The authorizer's checks are ANDed: signature and `iss` from discovery, then `aud` (if configured), `client_id` (if configured),
`scope` (if configured), and any **custom claim** rules (`custom_claim` with `EQUALS` / `CONTAINS` / `CONTAINS_ANY`).

Notes:
- Least privilege for inbound access means **scopes per capability** (`advisor.invoke`, `reports.submit`, …), not one "agent" scope.
- A JWT-authorized runtime rejects SigV4 calls. To serve an internal service with IAM, see S4.
- `request_header_allowlist = ["Authorization"]` lets the agent read the verified token's claims. The runtime has already validated
  it, so the agent can trust `client_id`/`sub` without re-verifying.
