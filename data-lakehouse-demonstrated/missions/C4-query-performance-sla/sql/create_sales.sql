CREATE TABLE IF NOT EXISTS riverbend_lakehouse.sales (
  sale_id     bigint,
  sold_at     timestamp,
  store_id    string,
  region      string,
  product_id  string,
  quantity    int,
  amount      double
)
PARTITIONED BY (day(sold_at))
LOCATION 's3://{{LAKE_BUCKET}}/warehouse/sales/'
TBLPROPERTIES ('table_type' = 'ICEBERG', 'format' = 'parquet', 'write_target_data_file_size_bytes' = '131072');
