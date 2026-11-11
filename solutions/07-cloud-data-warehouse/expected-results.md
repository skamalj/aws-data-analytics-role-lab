# Lab 07: check values

| Check | Value |
|---|---|
| `fact_sales` rows | **200,000**, with 0 load errors |
| `dim_customer` / `dim_product` rows | 500 / 18 |
| `archive.orders_2023` rows | **50,000**, completed revenue **7,458,664.50** |

**4.2 Completed revenue per quarter, 2024**

| quarter | revenue |
|---|---|
| 1 | 7404297.50 |
| 2 | 7505709.25 |
| 3 | 7465649.40 |
| 4 | 7550908.15 |

The largest category in every quarter is **Tents**. The full year is 8,998,076.70, the same as Lab 02, because it's the same data.

**5.1 Lifetime top 5 (2023 + 2024, completed)**

| customer_id | name | tier | lifetime_revenue |
|---|---|---|---|
| C00221 | Nia Evans | bronze | 90380.55 |
| C00297 | Dara Kim | gold | 90012.10 |
| C00417 | Ben Moreau | silver | 88715.40 |
| C00274 | Fatima Moreau | gold | 87863.25 |
| C00106 | Gus Hughes | bronze | 87295.85 |

**6** `mv_daily_region_sales` for 2024-07-04, EU: revenue **23,379.15**.
