-- Lab 09 Athena (workgroup cq-da-09). Replace __EVENTS_BUCKET__ (solve.sh does it).
CREATE EXTERNAL TABLE IF NOT EXISTS riverbend_stream.clickstream (
  event_id    string,
  event_ts    string,
  customer_id string,
  session_id  string,
  product_id  string,
  device      string,
  region      string,
  price       double,
  `query`     string
)
PARTITIONED BY (event_type string, dt date, hour int)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://__EVENTS_BUCKET__/events/'
TBLPROPERTIES (
  'projection.enabled'          = 'true',
  'projection.event_type.type'  = 'enum',
  'projection.event_type.values'= 'page_view,search,add_to_cart,checkout',
  'projection.dt.type'          = 'date',
  'projection.dt.format'        = 'yyyy-MM-dd',
  'projection.dt.range'         = 'NOW-7DAYS,NOW',
  'projection.hour.type'        = 'integer',
  'projection.hour.range'       = '0,23',
  'projection.hour.digits'      = '2',
  'storage.location.template'   = 's3://__EVENTS_BUCKET__/events/event_type=${event_type}/dt=${dt}/hour=${hour}/'
);

-- Event mix today: expect roughly 70% page_view, 15% add_to_cart, 10% search, 5% checkout
SELECT event_type, COUNT(*) AS events,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM riverbend_stream.clickstream
WHERE dt = current_date
GROUP BY event_type
ORDER BY events DESC;

-- Funnel by region: cart-to-checkout conversion and checkout value
SELECT region,
       COUNT_IF(event_type = 'add_to_cart') AS carts,
       COUNT_IF(event_type = 'checkout')    AS checkouts,
       ROUND(100.0 * COUNT_IF(event_type = 'checkout') / NULLIF(COUNT_IF(event_type = 'add_to_cart'), 0), 1) AS cart_to_checkout_pct,
       SUM(CASE WHEN event_type = 'checkout' THEN price END) AS checkout_value
FROM riverbend_stream.clickstream
WHERE dt = current_date AND event_type IN ('add_to_cart', 'checkout')
GROUP BY region
ORDER BY region;

-- End-to-end latency: how old is the newest event that has reached S3?
SELECT max(from_iso8601_timestamp(event_ts)) AS newest_event_in_s3,
       current_timestamp AS now_utc
FROM riverbend_stream.clickstream
WHERE dt = current_date AND event_type = 'page_view';
