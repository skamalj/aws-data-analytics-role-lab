-- Lab 05 checks (workgroup cq-da-05)
SELECT order_date, COUNT(*) AS orders, ROUND(SUM(total_amount), 2) AS revenue
FROM riverbend_curated.orders
WHERE order_date BETWEEN DATE '2024-07-01' AND DATE '2024-07-31'
GROUP BY order_date
ORDER BY order_date;

SELECT COUNT(*) AS rows_total, COUNT(DISTINCT order_id) AS distinct_orders
FROM riverbend_curated.orders
WHERE order_date BETWEEN DATE '2024-07-01' AND DATE '2024-07-31';

SELECT source_file, order_id, "_corrupt" AS raw_line
FROM riverbend_curated.orders_quarantine;
