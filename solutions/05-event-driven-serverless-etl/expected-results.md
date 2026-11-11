# Lab 05: check values

After `drop_files.py` (days 1–3) and `drop_files.py --bad` (day 4), the first check query returns:

| order_date | orders (non-cancelled, de-duplicated) | revenue (all curated rows) |
|---|---|---|
| 2024-07-01 | 282 | 49936.85 |
| 2024-07-02 | 306 | 49385.15 |
| 2024-07-03 | 293 | 44393.20 |
| 2024-07-04 | 290 | 48120.40 |

- **Total curated rows: 1,171**, and `distinct_orders` is also 1,171.
  - **1,184** means you didn't de-duplicate. Day 2 repeats 15 lines, 13 of them non-cancelled.
  - **1,200** means you didn't drop `CANCELLED` orders.
- **Quarantine: exactly 5 rows**, all from `orders_2024-07-04.csv`.
- 4 Glue job runs, all `SUCCEEDED`. A file with bad rows must **not** fail the job.
