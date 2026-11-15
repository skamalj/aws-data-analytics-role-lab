# Challenge C7 solution: Streaming upserts into Iceberg are failing

```bash
patch -p1 < solutions/C7-firehose-iceberg-upserts/fix.patch
./scripts/deploy.sh C7
python3 missions/C7-firehose-iceberg-upserts/scenarios/stream_orders.py
python3 missions/C7-firehose-iceberg-upserts/scenarios/check.py
```

| # | Symptom | Fault | Fix |
|---|---|---|---|
| 1 | Nothing lands. Error objects and logs show an access-denied error on the Glue catalog | The delivery role has `glue:GetTable` / `GetDatabase` but not **`glue:UpdateTable`**. Firehose writes data and metadata files, then can't commit the new metadata pointer | Add `glue:UpdateTable` (the role also needs S3 Get/Put/Delete/List on the table location, which it has) |
| 2 | Every event becomes a new row | **`append_only = true`**: Firehose ignores the operation and appends | `append_only = false` |
| 3 | (After 2) updates and deletes fail into the error prefix | Updates and deletes need to know which row to change: no **`unique_keys`** in `destination_table_configuration` | `unique_keys = ["order_id"]` |
| 4 | Still duplicates, and deletes never apply | The JQ query reads `.operation`, but the producer sends `op`. A missing operation means **insert** | `operation: .op` |

Expected after the fix: 180 rows (200 inserted, 20 deleted), one per `order_id`. 60 are `DELIVERED`, 60 are `PAID`/`SHIPPED` from wave 2, and 60 are still `PLACED`.

How Firehose upserts into Iceberg:
- With `unique_keys`, `update` is a delete of the matching key followed by an insert. Firehose writes Iceberg equality-delete files.
- `delete` needs only the key fields.
- Upsert tables accumulate delete files, so schedule compaction (`OPTIMIZE … REWRITE DATA USING BIN_PACK`, or a Glue table optimizer), as in C4.
- Routing can be static (`destination_table_configuration`), JQ on the record (metadata extraction, as here), or a Lambda that sets `otfMetadata`.
- The unique keys for a table always come from `destination_table_configuration`.
