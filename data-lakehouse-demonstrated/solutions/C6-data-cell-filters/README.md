# Challenge C6 solution: Row- and column-level access for marketing and regional managers

```bash
patch -p1 < solutions/C6-data-cell-filters/fix.patch
./scripts/deploy.sh C6
python3 missions/C6-data-cell-filters/scenarios/check.py
```

| # | Symptom | Fault | Fix |
|---|---|---|---|
| 1 | Marketing sees opted-out customers | The `marketing_opted_in` filter has `row_filter { all_rows_wildcard {} }` | `filter_expression = "marketing_opt_in = true"` (a boolean, not the string `'true'`) |
| 2 | Marketing sees `lifetime_value` | The exclude list only names `credit_score` | `excluded_column_names = ["credit_score", "lifetime_value"]` |
| 3 | The EU manager sees all regions and `credit_score` | The grant is SELECT **on the table**, so the `region_eu` filter is never used | Grant SELECT on the `region_eu` **data cell filter** (`data_cells_filter { … }`) |
| 4 | After fix 3, the EU manager sees 0 rows | `region = 'eu'`, but the data stores `EU`. String comparison is case-sensitive | `region = 'EU'` |

Expected after the fix: marketing sees 338 rows and 6 columns. The EU manager sees 150 rows (lifetime value 447,723.91) and 7 columns.

Notes for the exam:
- Grants on different filters (or on a filter plus the table) for the same principal are **unioned**. One broad grant cancels every filter.
- A filter can also be granted to an LF-Tag-based policy's principals. Filters are table-specific, while LF-Tags scale across tables (C5).
- Row filters use a PartiQL subset: `=`, `<>`, `<`, `>`, `IN`, `LIKE`, `AND`, `OR`, `IS NULL`, … on top-level columns.
