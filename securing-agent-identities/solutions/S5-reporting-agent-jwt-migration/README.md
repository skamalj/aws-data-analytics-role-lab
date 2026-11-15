# Challenge S5 solution: Anyone can file as anyone

```bash
patch -p1 < solutions/S5-reporting-agent-jwt-migration/fix.patch
./scripts/deploy.sh S5
python3 missions/S5-reporting-agent-jwt-migration/scenarios/check.py
```

| # | Symptom | Fault | Fix |
|---|---|---|---|
| 1 | The Compliance Portal can't get a token (`invalid_scope`) | Its app client allows only `reports.read` | Add `larchmont/reports.submit` to `allowed_oauth_scopes` |
| 2 | Anyone with IAM invoke permission can file, the legacy batch job included | No `authorizer_configuration`, so the runtime is IAM-authorized | `custom_jwt_authorizer` with the workforce discovery URL, `allowed_clients = [compliance portal]` and `allowed_scopes = [reports.submit]`. That alone rejects SigV4 |
| 3 | `"acting_as": "cfo"` still ends up in the record | `IDENTITY_MODE = payload`: the agent trusts the body | `IDENTITY_MODE = jwt` |
| 4 | Now the agent says "cannot determine who is filing" | The runtime doesn't pass `Authorization` to the agent unless allow-listed | `request_header_configuration { request_header_allowlist = ["Authorization"] }` |

Expected after the fix:
- The Compliance Portal files as its own `client_id`, with `identity_source: jwt`.
- The advisor token, the forged (`alg: none`) token and the legacy SigV4 job all get 401/403.

The migration principle: **identity must come from something the platform verified**, not from data the caller sends.
- With JWT inbound, the runtime checks the token before your code runs. It then obtains a workload access token bound to that user
  (`GetWorkloadAccessTokenForJWT`), so downstream calls through the token vault are made **for that user**.
- With SigV4 and `runtimeUserId` (S4), the identity is only as trustworthy as the caller allowed to name it.

Rollout notes:
- Changing the authorizer closes the SigV4 path immediately. Move legacy callers first, or run a second, IAM-only runtime for them
  during the transition.
- Delete the retired batch role, or remove its invoke permission, so it can't be re-enabled by mistake.
