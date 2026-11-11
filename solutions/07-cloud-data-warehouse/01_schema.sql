-- Lab 07 task 2: star schema. Small dimensions are copied to every node (DISTSTYLE ALL);
-- the fact table is distributed on the most common join key and sorted on the most common filter.
DROP MATERIALIZED VIEW IF EXISTS mv_daily_region_sales;
DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS stg_orders;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_product;

CREATE TABLE dim_customer (
  customer_id   VARCHAR(10) PRIMARY KEY,
  first_name    VARCHAR(40),
  last_name     VARCHAR(40),
  email         VARCHAR(100),
  phone         VARCHAR(20),
  city          VARCHAR(40),
  country       CHAR(2),
  region        VARCHAR(10),
  signup_date   DATE,
  loyalty_tier  VARCHAR(10)
) DISTSTYLE ALL;

CREATE TABLE dim_product (
  product_id    VARCHAR(10) PRIMARY KEY,
  product_name  VARCHAR(60),
  category      VARCHAR(20),
  unit_price    DECIMAL(10,2)
) DISTSTYLE ALL;

-- Raw landing table, same layout as the files
CREATE TABLE stg_orders (
  order_id      VARCHAR(10),
  order_ts      TIMESTAMP,
  customer_id   VARCHAR(10),
  product_id    VARCHAR(10),
  quantity      SMALLINT,
  unit_price    DECIMAL(10,2),
  discount      DECIMAL(4,2),
  total_amount  DECIMAL(12,2),
  channel       VARCHAR(10),
  store_id      VARCHAR(5),
  region        VARCHAR(10),
  status        VARCHAR(10)
);

CREATE TABLE fact_sales (
  order_id      VARCHAR(10) PRIMARY KEY,
  order_date    DATE NOT NULL,
  order_ts      TIMESTAMP NOT NULL,
  customer_id   VARCHAR(10) NOT NULL REFERENCES dim_customer(customer_id),
  product_id    VARCHAR(10) NOT NULL REFERENCES dim_product(product_id),
  quantity      SMALLINT,
  unit_price    DECIMAL(10,2),
  discount      DECIMAL(4,2),
  total_amount  DECIMAL(12,2),
  channel       VARCHAR(10),
  store_id      VARCHAR(5),
  region        VARCHAR(10),
  status        VARCHAR(10)
)
DISTKEY (customer_id)
COMPOUND SORTKEY (order_date, region);
