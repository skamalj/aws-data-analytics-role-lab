-- Lab 01 solution queries. Run in workgroup cq-da-01, database riverbend_raw.

-- 4.1 Revenue and order count per region
SELECT region,
       COUNT(*)                     AS orders,
       ROUND(SUM(total_amount), 2)  AS revenue
FROM riverbend_raw.orders
WHERE status = 'COMPLETED'
GROUP BY region
ORDER BY revenue DESC;

-- 4.2 Top 5 products by revenue
SELECT p.product_name,
       p.category,
       ROUND(SUM(o.total_amount), 2) AS revenue
FROM riverbend_raw.orders o
JOIN riverbend_raw.products p ON o.product_id = p.product_id
WHERE o.status = 'COMPLETED'
GROUP BY p.product_name, p.category
ORDER BY revenue DESC
LIMIT 5;

-- 4.3 Revenue per month
SELECT date_trunc('month', CAST(order_ts AS timestamp)) AS month,
       ROUND(SUM(total_amount), 2)                      AS revenue
FROM riverbend_raw.orders
WHERE status = 'COMPLETED'
GROUP BY 1
ORDER BY 1;

-- 4.4 Customers and average revenue per customer by loyalty tier.
-- LEFT JOIN so customers with no completed orders still count (revenue 0).
SELECT c.loyalty_tier,
       COUNT(*)                                     AS customers,
       ROUND(AVG(COALESCE(s.revenue, 0)), 2)        AS avg_revenue_per_customer
FROM riverbend_raw.customers c
LEFT JOIN (
    SELECT customer_id, SUM(total_amount) AS revenue
    FROM riverbend_raw.orders
    WHERE status = 'COMPLETED'
    GROUP BY customer_id
) s ON c.customer_id = s.customer_id
GROUP BY c.loyalty_tier
ORDER BY customers DESC;
