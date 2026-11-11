# Lab 02: check values

| Check | Value |
|---|---|
| Task 1/3: EU, March 2024, completed | **4,034 orders, 671,768.25 revenue** |
| Task 1 data scanned (CSV) | about 16 MB (all 12 files) |
| Task 3 data scanned (Parquet) | well under 1 MB (one partition, three columns) |
| Partitions in `orders_parquet` | 12 (`order_year=2024/order_month=1` … `12`) |
| Completed orders in 2024 | 180,134, revenue 29,926,564.30 |

**5.1 Revenue by category, 2024**

| category | revenue |
|---|---|
| Tents | 8998076.70 |
| Packs | 6063862.20 |
| Footwear | 4453570.35 |
| Climbing | 4085068.80 |
| Apparel | 3938249.05 |
| Cooking | 2387737.20 |

**5.2 Top countries, December 2024**

| country | revenue |
|---|---|
| US | 435898.60 |
| PE | 178442.45 |
| MX | 160085.40 |

**Task 6:** the CSV query fails with
`Query cancelled! : Bytes scanned limit was exceeded`. The Parquet query succeeds.
