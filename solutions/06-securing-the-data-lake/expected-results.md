# Lab 06: check values

| Who | Query | Expected |
|---|---|---|
| marketing / eu-analyst, **before** | any `SELECT` | Fails with an S3 `Access Denied`. The roles have no S3 permissions on the lake |
| marketing | `SELECT * FROM customers` | Works. **8 columns**, no `email` and no `phone`. 500 rows |
| marketing | `SELECT * FROM orders` | Fails with an insufficient Lake Formation permission error |
| eu-analyst | orders grouped by region | **One row: EU, 1,315 orders**, completed revenue **198,276.65** |
| eu-analyst | customers grouped by region | **One row: EU, 132 customers** |
| eu-analyst | `SELECT phone FROM customers` | Fails, because the column isn't visible to this role |
| eu-analyst | `SELECT email FROM customers` | Works, EU rows only |
| you (admin), after task 3 | `SELECT * FROM customers` | Fails until you grant yourself `SELECT`. Being a data lake admin does not grant data access by itself |
