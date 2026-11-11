# Lab 06 solution: Securing the Data Lake

`./solutions/06-securing-the-data-lake/solve.sh` applies everything.
`cleanup.sh` **reverts every Lake Formation change**, including the original admin list.

## The model

```
             IAM policy                        Lake Formation grants
persona ──► athena:*, glue:Get*, ──► Athena ──► "may this principal SELECT these columns/rows?"
            lakeformation:GetDataAccess          │ yes: LF vends temporary S3 credentials
                                                 ▼   scoped to the registered location
                                              s3://lake/ (registered; personas have no S3 IAM access)
```

Before the lab, the catalog uses the backwards-compatible setting: the special
group **`IAMAllowedPrincipals`** has `ALL` on the database and its tables, so
plain IAM policies decide who gets access. Securing the lake means:

1. **Data lake administrator** (task 1). This principal can manage grants. It
   doesn't automatically get data access.
2. **Register the S3 location** (task 2). Lake Formation can now vend
   credentials for it through the service-linked role
   `AWSServiceRoleForLakeFormationDataAccess`.
3. **Revoke `IAMAllowedPrincipals`** from the database and its tables, and clear the
   database's *default permissions for new tables* (task 3). From now on, only LF
   grants count for these tables. This is per database, so other databases in your
   account are unaffected. Don't change the *account-wide* defaults in Settings for this lab.
4. **Grant** (tasks 4–5):

| Persona | Grant | LF feature |
|---|---|---|
| marketing | `DESCRIBE` on database; `SELECT` on `customers` excluding `email`, `phone` | Column-level security (`TableWithColumns` + `ExcludedColumnNames`) |
| eu-analyst | `SELECT` on filter `orders_eu_only` (`region = 'EU'`, all columns) | Row-level security (data cells filter) |
| eu-analyst | `SELECT` on filter `customers_eu_no_phone` (`region = 'EU'`, excluding `phone`) | Cell-level security (rows and columns) |

## Console path

Lake Formation console:
- **Administrative roles and tasks > Data lake administrators > Add**: yourself.
- **Data lake locations > Register location**: `s3://<LakeBucket>`, service-linked role, *Lake Formation* permission mode.
- **Data permissions**: select `IAMAllowedPrincipals`, then **Revoke** on `riverbend_secure` and on *All tables*.
  **Databases > riverbend_secure > Edit**: untick *Use only IAM access control for new tables*.
- **Data filters > Create new filter**: `orders_eu_only` and `customers_eu_no_phone`.
- **Data permissions > Grant**: as in the table above.

Test with `labs/06-securing-the-data-lake/infra/as_role.sh <persona> "<sql>"`.

## Things that commonly go wrong

- *"Insufficient Lake Formation permission(s)"* for **you** after task 3: grant
  yourself `SELECT` if you want to query. Admin status isn't data access.
- *Access denied on S3* for a persona even after grants: the location isn't
  registered, or it's registered in hybrid mode without the principal opted in.
- Glue crawlers and Glue ETL jobs now also need LF grants (`CREATE_TABLE`,
  `ALTER`, `DATA_LOCATION_ACCESS`) on this database.
- `cleanup.sh` re-grants `IAMAllowedPrincipals` **before** removing you as
  admin. Otherwise CloudFormation couldn't delete the Glue tables.

## DIY: LF-Tags (tag-based access control)

Instead of naming tables in grants, create an LF-Tag `sensitivity = {public, pii}`,
tag `customers.email`/`customers.phone` as `pii` and everything else `public`,
then grant marketing `SELECT` on *resources matching `sensitivity=public`*.
New tables are then protected as soon as they're tagged.
