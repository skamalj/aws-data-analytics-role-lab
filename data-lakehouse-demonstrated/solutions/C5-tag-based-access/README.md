# Challenge C5 solution: Tag-based access for data science and interns

```bash
patch -p1 < solutions/C5-tag-based-access/fix.patch
./scripts/deploy.sh C5
python3 missions/C5-tag-based-access/scenarios/check.py
```

| # | Symptom | Fault | Fix |
|---|---|---|---|
| 1 | Data science reads `payroll` | The data scientist expression is only `sensitivity IN (public, confidential)`. `payroll` is confidential, so it matches | Add a second key, `domain IN (web, customer)`. Keys are ANDed |
| 2 | The intern reads `customers` | The intern expression was copied from data science's domain list: `domain IN (web, customer)` matches every customer table regardless of sensitivity | `sensitivity IN (public)` |
| 3 | Data science sees `phone` | Only `email` has the column-level `sensitivity = pii` tag. `phone` inherits the table's `confidential` | Tag both `email` and `phone` with `pii` |
| 4 | Nobody sees `product_reviews` (once 1–2 are fixed) | The table has `domain` but no `sensitivity` tag, so no expression that tests `sensitivity` can match it | Add `sensitivity = public` |

How LF-TBAC evaluates: a grant `{domain: [web, customer]} AND {sensitivity: [public, confidential]}` gives SELECT on every table, and every
column, whose effective tags satisfy all keys. A column's effective tag is its own tag, else the table's tag, else the database's tag.
That's why tagging two columns `pii` removes them from a "confidential" grant without a separate column grant.

What the environment did for you (and the exam may not): it registered `s3://<lake>/governed/c5/` with a Lake Formation role, and it revoked
`IAMAllowedPrincipals` on the database and tables. With `IAMAllowedPrincipals` in place, IAM policies alone govern access and LF grants
are bypassed. Personas also need `lakeformation:GetDataAccess` in IAM so Lake Formation can vend S3 credentials to Athena.
