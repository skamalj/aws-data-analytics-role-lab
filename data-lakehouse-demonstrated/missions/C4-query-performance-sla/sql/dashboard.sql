-- Q1: March revenue by region (finance dashboard, first tile)
SELECT region, round(sum(amount), 2) AS revenue
FROM riverbend_lakehouse.sales
WHERE date_format(sold_at, '%Y-%m') = '2026-03'
GROUP BY region
ORDER BY revenue DESC;

-- Q2: top 3 products in the last week of March
SELECT *
FROM (SELECT product_id, round(sum(amount), 2) AS revenue
      FROM riverbend_lakehouse.sales
      WHERE date_format(sold_at, '%Y-%m-%d') BETWEEN '2026-03-25' AND '2026-03-31'
      GROUP BY product_id)
ORDER BY revenue DESC
LIMIT 3;

-- Q3: one store, one day (store manager view)
SELECT round(sum(amount), 2) AS revenue, count(*) AS sales
FROM riverbend_lakehouse.sales
WHERE format_datetime(sold_at, 'yyyy-MM-dd') = '2026-03-15' AND store_id = 'S07';
