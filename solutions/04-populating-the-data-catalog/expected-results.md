# Lab 04: check values

| Check | Value |
|---|---|
| Tables created by crawler | `lnd_web_orders`, `lnd_store_sales`, `lnd_returns` (exactly 3) |
| `lnd_web_orders` rows (Jan–Jun) | **2,974** across 6 partitions |
| `lnd_store_sales` rows | **2,026**, columns `order_id … total_amount` |
| `lnd_returns` rows / total refunds | **319** / **54,346.15** (both files) |
| After `add_month.py` + re-crawl | 7 partitions, **3,454** web orders |

**Web orders per month** (`month` partition values are strings `'01'` to `'06'`)

| month | orders |
|---|---|
| 01 | 514 |
| 02 | 455 |
| 03 | 473 |
| 04 | 519 |
| 05 | 531 |
| 06 | 482 |

**Task 5: clickstream on 2024-06-03**

| event_type | events |
|---|---|
| page_view | 1409 |
| add_to_cart | 288 |
| search | 215 |
| checkout | 88 |

If month 03 has 50 extra rows, or a table such as `lnd_month_03`, the `.tmp` file wasn't excluded.
