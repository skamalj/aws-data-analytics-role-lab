-- Task 4: clickstream table with partition projection. Replace __LANDING_BUCKET__.
CREATE EXTERNAL TABLE IF NOT EXISTS riverbend_catalog.clickstream (
  event_id    string,
  event_ts    string,
  event_type  string,
  customer_id string,
  product_id  string,
  device      string
)
PARTITIONED BY (dt date)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://__LANDING_BUCKET__/clickstream/'
TBLPROPERTIES (
  'projection.enabled'        = 'true',
  'projection.dt.type'        = 'date',
  'projection.dt.format'      = 'yyyy/MM/dd',
  'projection.dt.range'       = '2024/01/01,NOW',
  'projection.dt.interval'    = '1',
  'projection.dt.interval.unit' = 'DAYS',
  'storage.location.template' = 's3://__LANDING_BUCKET__/clickstream/${dt}/'
);

-- Task 5
SELECT event_type, COUNT(*) AS events
FROM riverbend_catalog.clickstream
WHERE dt = DATE '2024-06-03'
GROUP BY event_type
ORDER BY events DESC;

-- Checks for task 3
SELECT COUNT(*) AS web_orders FROM riverbend_catalog.lnd_web_orders;
SELECT COUNT(*) AS store_sales FROM riverbend_catalog.lnd_store_sales;
SELECT COUNT(*) AS returns_rows, ROUND(SUM(refund_amount), 2) AS refunds FROM riverbend_catalog.lnd_returns;
SELECT month, COUNT(*) AS orders FROM riverbend_catalog.lnd_web_orders GROUP BY month ORDER BY month;
