-- Lab 02 solution. Replace __CURATED_BUCKET__ (solve.sh does this for you).

-- Task 1: baseline on raw CSV (scans every file, ~16 MB)
SELECT COUNT(*) AS orders, ROUND(SUM(total_amount), 2) AS revenue
FROM riverbend_lake.orders_csv
WHERE status = 'COMPLETED' AND region = 'EU'
  AND order_ts >= TIMESTAMP '2024-03-01 00:00:00'
  AND order_ts <  TIMESTAMP '2024-04-01 00:00:00';

-- Task 2: CTAS to a partitioned Parquet table
CREATE TABLE riverbend_lake.orders_parquet
WITH (
  format = 'PARQUET',
  write_compression = 'SNAPPY',
  external_location = 's3://__CURATED_BUCKET__/orders_parquet/',
  partitioned_by = ARRAY['order_year', 'order_month']
) AS
SELECT order_id, order_ts, customer_id, product_id, quantity, unit_price,
       discount, total_amount, channel, store_id, region, status,
       year(order_ts)  AS order_year,
       month(order_ts) AS order_month
FROM riverbend_lake.orders_csv;

SHOW PARTITIONS riverbend_lake.orders_parquet;

-- Task 3: same question, with partition pruning and column pruning
SELECT COUNT(*) AS orders, ROUND(SUM(total_amount), 2) AS revenue
FROM riverbend_lake.orders_parquet
WHERE status = 'COMPLETED' AND region = 'EU'
  AND order_year = 2024 AND order_month = 3;

-- Task 4: analyst view
CREATE OR REPLACE VIEW riverbend_lake.v_order_details AS
SELECT o.order_id, o.order_ts, o.order_year, o.order_month,
       o.customer_id, c.country, c.loyalty_tier,
       o.product_id, p.product_name, p.category,
       o.quantity, o.unit_price, o.discount, o.total_amount,
       o.channel, o.store_id, o.region, o.status
FROM riverbend_lake.orders_parquet o
LEFT JOIN riverbend_lake.products  p ON o.product_id  = p.product_id
LEFT JOIN riverbend_lake.customers c ON o.customer_id = c.customer_id;

-- Task 5.1: revenue per category
SELECT category, ROUND(SUM(total_amount), 2) AS revenue
FROM riverbend_lake.v_order_details
WHERE status = 'COMPLETED' AND order_year = 2024
GROUP BY category
ORDER BY revenue DESC;

-- Task 5.2: top 3 countries in December
SELECT country, ROUND(SUM(total_amount), 2) AS revenue
FROM riverbend_lake.v_order_details
WHERE status = 'COMPLETED' AND order_year = 2024 AND order_month = 12
GROUP BY country
ORDER BY revenue DESC
LIMIT 3;
