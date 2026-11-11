-- Lab 12: the numbers your dashboard must show (Athena, workgroup cq-da-12)
SELECT ROUND(SUM(total_amount), 2) AS completed_revenue, COUNT(*) AS completed_orders
FROM riverbend_bi.v_sales WHERE status = 'COMPLETED';

SELECT channel, ROUND(SUM(total_amount), 2) AS revenue
FROM riverbend_bi.v_sales WHERE status = 'COMPLETED'
GROUP BY channel ORDER BY revenue DESC;

SELECT date_format(order_date, '%Y-%m') AS month, ROUND(SUM(total_amount), 2) AS revenue
FROM riverbend_bi.v_sales WHERE status = 'COMPLETED'
GROUP BY 1 ORDER BY 1;

SELECT region, ROUND(SUM(total_amount), 2) AS revenue
FROM riverbend_bi.v_sales WHERE status = 'COMPLETED'
GROUP BY region ORDER BY revenue DESC;
