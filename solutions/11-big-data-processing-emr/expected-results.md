# Lab 11: check values

Input: 172,449 events from 2024-06-01 to 2024-06-15. A few events land just after midnight on the 15th.

| Check | Value |
|---|---|
| Sessions | **20,374** |
| Converted sessions (at least one checkout) | **3,658**, so conversion is **17.95%** |
| Average duration / events per session | **719.3 s** / **8.46** |
| Bounce sessions (exactly 1 event) | **1,323** |
| Sessions with dt 2024-06-01 / 2024-06-14 / 2024-06-15 | **1,464** / **1,455** / **0**. Sessions belong to their *start* date |

| device | sessions | conversion_pct | avg_duration_s |
|---|---|---|---|
| desktop | 5047 | 23.76 | 721.0 |
| ios | 8119 | 19.09 | 724.2 |
| android | 7208 | 12.61 | 712.5 |

Common wrong answers:
- **About 21,000 sessions**: you sessionized by customer only within each day, or split at midnight.
  Sessions near midnight and overlapping sessions of the same customer and device merge under the 30-minute rule.
- **Sessions on 2024-06-15**: you used the event's date or the input `dt` partition, not the session start.
- **Fewer sessions**: you grouped by customer without `device`.
