-- Iceberg target for the order-status stream (run by setup.py through Athena)
CREATE TABLE IF NOT EXISTS riverbend_lakehouse.order_status (
  order_id   string,
  status     string,
  amount     double,
  updated_at string
)
LOCATION 's3://{{LAKE_BUCKET}}/warehouse/order_status/'
TBLPROPERTIES ('table_type' = 'ICEBERG', 'format' = 'parquet', 'write_compression' = 'zstd');
