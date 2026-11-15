CREATE TABLE IF NOT EXISTS riverbend_lakehouse.vendor_shipments (
  shipment_id  string,
  vendor_id    string,
  product_id   string,
  quantity     int,
  shipped_at   timestamp,
  source_file  string
)
LOCATION 's3://{{LAKE_BUCKET}}/warehouse/vendor_shipments/'
TBLPROPERTIES ('table_type' = 'ICEBERG', 'format' = 'parquet');
