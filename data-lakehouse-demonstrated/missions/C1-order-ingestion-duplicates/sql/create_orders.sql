CREATE TABLE IF NOT EXISTS riverbend_lakehouse.orders (
  order_id     string,
  customer_id  string,
  product_id   string,
  quantity     int,
  amount       double,
  region       string,
  status       string,
  order_ts     timestamp,
  updated_at   timestamp
)
PARTITIONED BY (day(order_ts))
LOCATION 's3://{{LAKE_BUCKET}}/warehouse/orders/'
TBLPROPERTIES ('table_type' = 'ICEBERG', 'format' = 'parquet');
