# Challenge C5: Tag-based access for data science and interns

**Exam objective:** *Configure tag-based access control for data science and intern roles*
**Services:** AWS Lake Formation (LF-Tags, LF-TBAC grants, column-level tags, registered locations), Amazon Athena, AWS Glue Data Catalog, IAM
**Time:** 25–35 minutes  |  **Deploy:** `./scripts/deploy.sh C5`

> The deploy makes **you** a Lake Formation data lake administrator. It backs up your Data Lake settings first, and
> `./scripts/destroy.sh C5` restores them. It touches only the database `riverbend_governed_c5` and the prefix `s3://<lake>/governed/c5/`.

## Situation

The governance team classified `riverbend_governed_c5` with two LF-Tags: `domain` (`web`, `customer`, `hr`) and `sensitivity`
(`public`, `confidential`, `pii`). Access must be granted **by tag, not by table**, so new tables are covered automatically once they're tagged.

| Persona (IAM role) | Policy |
|---|---|
| `riverbend-lh-c5-data-scientist` | All **customer** and **web** data that is **public or confidential**. Never PII, never HR |
| `riverbend-lh-c5-intern` | **Public** data only |

| Table | Classification (per the data catalogue) |
|---|---|
| `web_sessions` | domain `web`, sensitivity `public` |
| `product_reviews` | domain `customer`, sensitivity `public` |
| `customers` | domain `customer`, sensitivity `confidential`. Columns `email` and `phone` are **pii** |
| `payroll` | domain `hr`, sensitivity `confidential` |

Complaints: an intern opened the customer table, data science can see payroll and customer phone numbers, and no one can find the
product reviews. The personas have no S3 permissions of their own. All data access comes through Lake Formation (the deploy has
already revoked `IAMAllowedPrincipals` on this database).

Everything is in [`terraform/main.tf`](terraform/main.tf).

## Explore and check

```bash
python3 missions/C5-tag-based-access/scenarios/probe.py     # what each persona sees, table by table
python3 missions/C5-tag-based-access/scenarios/check.py     # PASS/FAIL
```

Console: **Lake Formation → LF-Tags and permissions**, **Data permissions**, and **Tables → (table) → LF-Tags** (including column tags).

## Done when

`check.py` reports 10/10: both personas read the public tables, data science reads `customers` without `email` and `phone`, and every forbidden table is denied.

<details><summary>Hint 1</summary>An LF-Tag policy grant matches a resource when <b>every</b> key in the expression matches (AND across keys, OR across values). What does each persona's expression actually say?</details>
<details><summary>Hint 2</summary>A table with no value for a key in the expression never matches that expression. Check that every table is fully tagged.</details>
<details><summary>Hint 3</summary>Column tags override the table's tag for that column. Which PII columns are actually tagged <code>pii</code>?</details>
