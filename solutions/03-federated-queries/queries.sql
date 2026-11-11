-- Lab 03 solution queries. Replace __LAKE_BUCKET__ (solve.sh does it).

SELECT table_schema, table_name FROM ddb.information_schema.tables WHERE table_schema = 'default';

SELECT * FROM ddb."default".riverbend_customer_profiles LIMIT 10;

-- 4.1 opt-in by tier (DynamoDB only)
SELECT loyalty_tier,
       COUNT(*)                                          AS customers,
       COUNT_IF(marketing_opt_in)                        AS opted_in
FROM ddb."default".riverbend_customer_profiles
GROUP BY loyalty_tier
ORDER BY customers DESC;

-- 4.2 campaign list, top 10 (DynamoDB joined with S3)
WITH revenue AS (
  SELECT customer_id, SUM(total_amount) AS revenue
  FROM riverbend_fed.orders
  WHERE status = 'COMPLETED'
  GROUP BY customer_id
)
SELECT p.customer_id, p.full_name, p.email, p.loyalty_tier, ROUND(r.revenue, 2) AS revenue
FROM ddb."default".riverbend_customer_profiles p
JOIN revenue r ON p.customer_id = r.customer_id
WHERE p.marketing_opt_in = true
ORDER BY r.revenue DESC
LIMIT 10;

-- 4.3
SELECT COUNT(*) AS eu_gold_platinum_opted_in
FROM ddb."default".riverbend_customer_profiles
WHERE marketing_opt_in = true AND region = 'EU' AND loyalty_tier IN ('gold', 'platinum');

-- 5 export the full list as Parquet
CREATE TABLE riverbend_fed.campaign_list
WITH (format = 'PARQUET', external_location = 's3://__LAKE_BUCKET__/exports/campaign_list/') AS
WITH revenue AS (
  SELECT customer_id, SUM(total_amount) AS revenue
  FROM riverbend_fed.orders
  WHERE status = 'COMPLETED'
  GROUP BY customer_id
)
SELECT p.customer_id, p.full_name, p.email, p.preferred_channel, p.loyalty_tier,
       p.loyalty_points, ROUND(r.revenue, 2) AS revenue
FROM ddb."default".riverbend_customer_profiles p
JOIN revenue r ON p.customer_id = r.customer_id
WHERE p.marketing_opt_in = true;

SELECT COUNT(*) AS campaign_list_rows FROM riverbend_fed.campaign_list;
