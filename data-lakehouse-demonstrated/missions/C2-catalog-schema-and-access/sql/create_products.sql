CREATE TABLE IF NOT EXISTS riverbend_lakehouse.products (
  product_id    string,
  product_name  string,
  category      string,
  price         float,
  stock         int
)
PARTITIONED BY (bucket(16, product_id))
LOCATION 's3://{{LAKE_BUCKET}}/warehouse/products/'
TBLPROPERTIES ('table_type' = 'ICEBERG', 'format' = 'parquet');

DELETE FROM riverbend_lakehouse.products WHERE true;

INSERT INTO riverbend_lakehouse.products
SELECT 'SKU' || lpad(CAST(n AS varchar), 6, '0'),
       element_at(ARRAY['Trailhead','Summit','Ridge','Storm','Alpine','Everyday'], 1 + n % 6) || ' ' ||
       element_at(ARRAY['Tent','Boot','Jacket','Pack','Stove','Rope'], 1 + (n / 6) % 6) || ' ' || CAST(n AS varchar),
       element_at(ARRAY['Tents','Footwear','Apparel','Packs','Cooking','Climbing'], 1 + (n / 6) % 6),
       CAST(19 + n % 480 AS real),
       CAST(n % 250 AS integer)
FROM UNNEST(sequence(1, 60000)) AS t(n);
