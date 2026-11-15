# Challenge S1 solution: Any operator can act as any agent

```bash
patch -p1 < solutions/S1-workload-identity-abac/fix.patch
./scripts/deploy.sh S1
python3 missions/S1-workload-identity-abac/scenarios/check.py
```

| # | Symptom | Fault | Fix |
|---|---|---|---|
| 1 | Nobody can mint any token | The condition tests **`aws:RequestTag/team`**, the tags *sent in the request* (as in `TagResource`). `GetWorkloadAccessToken` sends none, so `StringEquals` never matches | `aws:ResourceTag/team` = `${aws:PrincipalTag/team}` |
| 2 | Compliance can't use its own agent | The compliance role is tagged `department = compliance`, so `${aws:PrincipalTag/team}` is empty | Tag the role `team = compliance` |
| 3 | Advisory can act as the reporting agent | `larchmont-s1-reporting-agent` is tagged `team = advisory` (copy-paste) | `team = compliance` |
| 4 | Any operator can take over any agent | The policy allows `TagResource` / `UntagResource` on `*`. A trading operator retags the advisor identity `team = trading` and passes the ABAC check | Remove them, plus an explicit **Deny** on both so another policy can't re-grant them. Tag changes belong to the platform pipeline (Terraform), not to operators |

Why the directory statement stays unconditioned: token operations are authorized against two resources, the workload identity
directory (`…:workload-identity-directory/default`) and the identity itself. The directory carries no team tag, so putting the ABAC
condition on it would deny everyone.

ABAC hardening beyond this challenge:
- If teams may label their own resources, constrain tagging with `aws:RequestTag/team = ${aws:PrincipalTag/team}` **and**
  `aws:ResourceTag/team = ${aws:PrincipalTag/team}` and `aws:TagKeys`. Keep principal tags (IAM role tags, session tags) out of operators' reach.
- Watch for tag tampering: challenge S6 alarms on `TagResource` / `UntagResource` against workload identities.
