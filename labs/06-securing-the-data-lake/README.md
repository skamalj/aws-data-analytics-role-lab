# Lab 06: Securing the Data Lake

## Scenario

Riverbend's lake now contains customer PII (email, phone). An upcoming audit
found that anyone with broad S3 and Athena IAM permissions can read everything.
The CISO's requirements:

| Persona | Must see | Must **not** see |
|---|---|---|
| **Marketing** | the customers table: names, city, country, region, tier | email, phone, and any order data |
| **EU analyst** | orders and customers for region `EU` only, including email | other regions' rows; any customer's phone number |

Access must be governed centrally with **AWS Lake Formation**, not by
hand-written S3 bucket policies per team.

## What the starting environment gives you

`./scripts/deploy.sh 06-securing-the-data-lake` creates:

| Resource | Notes |
|---|---|
| `LakeBucket` | `customers/customers.csv` (with PII), `orders/orders_2024_h1.csv` |
| Glue database `riverbend_secure` | Tables `customers` and `orders`, currently under IAM-only access control |
| Role `cq-da-06-marketing` | Athena + Glue read APIs + `lakeformation:GetDataAccess`. **No S3 access to the lake** |
| Role `cq-da-06-eu-analyst` | Same permissions as marketing |
| Athena workgroup `cq-da-06` | Both personas may use it |
| `infra/as_role.sh` | Runs a query as a persona: `./labs/06-securing-the-data-lake/infra/as_role.sh marketing "SELECT ..."` |

> **This lab changes Lake Formation settings in your account.** Run
> `solutions/06-securing-the-data-lake/cleanup.sh` at the end. It restores
> your original data lake administrator list. It's safest to use an account
> where you don't already use Lake Formation.

## Your tasks

0. Run `as_role.sh marketing "SELECT * FROM riverbend_secure.customers LIMIT 5"`. It fails. Note why.
1. Make your own IAM principal a **data lake administrator**. Keep any existing admins.
2. **Register** `s3://<LakeBucket>` with Lake Formation.
3. Stop IAM-only access for `riverbend_secure`: revoke `IAMAllowedPrincipals`
   on the database and its tables, and make sure new tables in this database don't default to IAM-only access.
4. **Marketing:** grant what's needed for the requirements above, using column-level permissions.
5. **EU analyst:** grant what's needed using **data filters**: a row filter on
   `orders`, and a row-and-column filter on `customers`.
6. **Verify** every row in the requirements table with `as_role.sh`, including the things each persona must *not* be able to do.
7. Question: after task 3, can **you** still query the tables? Why or why not?

## How you know you're done

Every check in [`expected-results.md`](../../solutions/06-securing-the-data-lake/expected-results.md) behaves as described.

## Hints

<details><summary>Principal names</summary>Lake Formation grants use IAM role ARNs. If you are signed in via SSO, your admin principal is the role behind your session (<code>arn:aws:iam::ACCOUNT:role/...</code>), not the <code>sts</code> assumed-role ARN.</details>
<details><summary>Filters</summary>A data filter can combine a row filter expression (<code>region = 'EU'</code>) with an included or excluded column list. You grant <code>SELECT</code> on the filter, not on the table.</details>

## DIY challenge

Re-implement the marketing rules with **LF-Tags** (`sensitivity=pii|public`) and tag-based grants.

## Cleanup

```bash
./solutions/06-securing-the-data-lake/cleanup.sh   # ALWAYS run this one
./scripts/destroy.sh 06-securing-the-data-lake
```

If you built the grants by hand, `cleanup.sh` still works. It revokes every
grant held by the two persona roles, deletes the two filters by their solution
names (delete any filter with a different name yourself), deregisters the
location and restores the admin list. That last step only works if the
backup was made, by `lf_admin.py add` or `solve.sh`. Otherwise, remove yourself
as admin manually.

**Cost:** about $0. Lake Formation has no charge for permissions, and the Athena scans are tiny.
