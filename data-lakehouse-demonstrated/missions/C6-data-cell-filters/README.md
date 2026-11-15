# Challenge C6: Row- and column-level access for marketing and regional managers

**Exam objective:** *Configure data cell filters for marketing and regional manager access*
**Services:** AWS Lake Formation (data cell filters, grants on filters), Amazon Athena, AWS Glue Data Catalog, IAM
**Time:** 20–30 minutes  |  **Deploy:** `./scripts/deploy.sh C6`

> As in C5, the deploy makes you a Lake Formation data lake administrator (with a backup) and `destroy.sh C6` restores the settings.
> Scope: database `riverbend_governed_c6` and `s3://<lake>/governed/c6/` only.

## Situation

`riverbend_governed_c6.customer_profiles` (600 customers) has these columns: `customer_id`, `name`, `email`, `region`, `segment`,
`marketing_opt_in` (boolean), `credit_score` and `lifetime_value`. One table, two audiences:

| Persona (IAM role) | Rows | Columns |
|---|---|---|
| `riverbend-lh-c6-marketing` | Only customers who **opted in** to marketing | Everything **except** `credit_score` and `lifetime_value` |
| `riverbend-lh-c6-eu-manager` | Only **EU** customers (region value `EU`) | Everything **except** `credit_score` |

Legal reports that marketing exported opted-out customers along with their lifetime value. The EU regional manager says they can see
every region and everyone's credit score.

Everything is in [`terraform/main.tf`](terraform/main.tf).

## Explore and check

```bash
python3 missions/C6-data-cell-filters/scenarios/probe.py
python3 missions/C6-data-cell-filters/scenarios/check.py
```

Console: **Lake Formation → Data filters** and **Data permissions**.

## Done when

`check.py` reports 8/8.

<details><summary>Hint 1</summary>A data cell filter has two halves: <b>which rows</b> (a row filter expression, or "all rows") and <b>which columns</b> (an include list or an exclude list). Check both halves of both filters against the table above.</details>
<details><summary>Hint 2</summary>A filter does nothing until a principal is granted SELECT <b>on the filter</b>. A SELECT grant on the table gives every row and column.</details>
<details><summary>Hint 3</summary>Row filter expressions are compared to the stored values exactly. What do the <code>region</code> values in the data look like?</details>
