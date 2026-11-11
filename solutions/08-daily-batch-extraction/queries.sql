-- Lab 08: lake-side view of the current state of every order (latest version wins)
CREATE OR REPLACE VIEW riverbend_extracts.orders_current AS
SELECT order_id, order_ts, customer_id, product_id, quantity, unit_price, discount,
       total_amount, channel, store_id, region, status, updated_at
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY updated_at DESC, extracted_at DESC) AS rn
  FROM riverbend_extracts.orders_changes
) t
WHERE rn = 1;

SELECT extract_date, COUNT(*) AS rows_in_extract
FROM riverbend_extracts.orders_changes
GROUP BY extract_date
ORDER BY extract_date;

SELECT status, COUNT(*) AS orders
FROM riverbend_extracts.orders_current
GROUP BY status
ORDER BY orders DESC;

SELECT COUNT(*) AS current_orders,
       SUM(CASE WHEN status = 'COMPLETED' THEN total_amount END) AS completed_revenue
FROM riverbend_extracts.orders_current;
