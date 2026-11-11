-- Lab 07 tasks 4-6
-- 4.1 Quarterly revenue by category (2024, completed orders)
SELECT DATE_PART(quarter, f.order_date) AS quarter,
       p.category,
       SUM(f.total_amount) AS revenue
FROM fact_sales f
JOIN dim_product p ON p.product_id = f.product_id
WHERE f.status = 'COMPLETED'
GROUP BY 1, 2
ORDER BY 1, 3 DESC;

-- 4.2 Quarter totals
SELECT DATE_PART(quarter, order_date) AS quarter, SUM(total_amount) AS revenue
FROM fact_sales WHERE status = 'COMPLETED'
GROUP BY 1 ORDER BY 1;

-- 5 Spectrum: the 2023 archive stays in S3 and is queried in place
CREATE EXTERNAL SCHEMA IF NOT EXISTS archive
FROM DATA CATALOG DATABASE 'riverbend_archive'
IAM_ROLE default;

SELECT COUNT(*) AS archive_rows, SUM(CASE WHEN status = 'COMPLETED' THEN total_amount END) AS revenue_2023
FROM archive.orders_2023;

-- 5.1 Lifetime (2023 + 2024) top 5 customers
WITH all_orders AS (
  SELECT customer_id, total_amount, status FROM fact_sales
  UNION ALL
  SELECT customer_id, CAST(total_amount AS DECIMAL(12,2)), status FROM archive.orders_2023
)
SELECT c.customer_id, c.first_name, c.last_name, c.loyalty_tier, SUM(a.total_amount) AS lifetime_revenue
FROM all_orders a
JOIN dim_customer c ON c.customer_id = a.customer_id
WHERE a.status = 'COMPLETED'
GROUP BY 1, 2, 3, 4
ORDER BY lifetime_revenue DESC
LIMIT 5;

-- 6 Materialized view for the operations dashboard
CREATE MATERIALIZED VIEW mv_daily_region_sales
AUTO REFRESH YES
AS
SELECT order_date, region, COUNT(*) AS orders, SUM(total_amount) AS revenue
FROM fact_sales
WHERE status = 'COMPLETED'
GROUP BY order_date, region;

SELECT * FROM mv_daily_region_sales WHERE order_date = '2024-07-04' ORDER BY region;
