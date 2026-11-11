# Lab 01: check values

The data is generated deterministically, so your numbers should match these
exactly (allow ±0.01 for rounding).

Whole dataset: 5,000 orders, of which 4,517 are `COMPLETED`, with total completed revenue of **731,227.40**.

**4.1 Revenue by region**

| region | orders | revenue |
|---|---|---|
| EU | 1197 | 198276.65 |
| LATAM | 1231 | 198112.55 |
| APAC | 1122 | 180116.25 |
| NA | 967 | 154721.95 |

**4.2 Top 5 products**

| product_name | category | revenue |
|---|---|---|
| Summit 4P Tent | Tents | 111034.35 |
| Expedition Pack 65L | Packs | 79189.25 |
| Dynamic Rope 60m | Climbing | 77723.10 |
| Trailhead 2P Tent | Tents | 59827.95 |
| Rain Shell Jacket | Apparel | 50053.90 |

**4.3 Revenue per month (2024)**

| month | revenue |
|---|---|
| 2024-01 | 127244.55 |
| 2024-02 | 114206.25 |
| 2024-03 | 116678.25 |
| 2024-04 | 130597.15 |
| 2024-05 | 127105.40 |
| 2024-06 | 115395.80 |

**4.4 Loyalty tiers** (customers with no completed order count as 0)

| loyalty_tier | customers | avg_revenue_per_customer |
|---|---|---|
| bronze | 232 | 1437.93 |
| silver | 154 | 1541.25 |
| gold | 89 | 1421.49 |
| platinum | 25 | 1350.48 |
