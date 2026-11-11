# Lab 03: check values

**4.1 Opt-in by tier**

| loyalty_tier | customers | opted_in |
|---|---|---|
| bronze | 232 | 144 |
| silver | 154 | 99 |
| gold | 89 | 60 |
| platinum | 25 | 19 |

**4.2 Campaign list, top 10**

| customer_id | full_name | loyalty_tier | revenue |
|---|---|---|---|
| C00179 | Fatima Hughes | gold | 4339.65 |
| C00105 | Tariq Dubois | bronze | 3834.50 |
| C00381 | Priya Okafor | silver | 3557.25 |
| C00012 | Nia Gupta | bronze | 3426.60 |
| C00009 | Gus Hughes | silver | 3374.85 |
| C00004 | Gus Hughes | bronze | 3369.10 |
| C00384 | Tariq Ito | silver | 3257.65 |
| C00063 | Fatima Berg | silver | 3171.95 |
| C00220 | Tariq Costa | silver | 3012.10 |
| C00002 | Priya Hughes | silver | 2965.55 |

(Emails follow the pattern `first.last<number>@example.com`, for example `fatima.hughes179@example.com`.)

**4.3** EU gold + platinum opted in: **23**

**5** `riverbend_fed.campaign_list` row count: **322** (every opted-in customer has at least one completed order).
