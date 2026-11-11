# Lab 08: check values

| extract_date | rows_in_extract | why |
|---|---|---|
| 2024-06-30 | **5,000** | full snapshot |
| 2024-07-01 | **312** | 300 new orders + 12 orders updated to RETURNED |
| 2024-07-02 | **312** | 300 new + 12 updated |

Re-running any date overwrites that partition, so the counts don't change. If 2024-07-01 shows 624, your job appends instead of overwriting.

**`orders_current`** (latest version of each order):

| status | orders |
|---|---|
| COMPLETED | 5028 |
| RETURNED | 390 |
| CANCELLED | 182 |

`current_orders` = **5,600**, `completed_revenue` = **816,012.20**.

If you see 5,624 current orders, or COMPLETED + RETURNED double-counted, your view doesn't keep only the latest version per `order_id`.

The state machine's final output looks like `{"run_date":"2024-07-01","mode":"incremental","rows":312}`, and the SNS topic receives a success message.
