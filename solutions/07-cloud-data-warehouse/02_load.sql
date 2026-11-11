-- Lab 07 task 3: load with COPY (parallel, from 4 gzip files), then ELT into the fact table.
-- IAM_ROLE default = the namespace's default role (cq-da-07-redshift-role).
COPY dim_customer FROM 's3://__STAGING_BUCKET__/stage/customers/'
IAM_ROLE default FORMAT AS CSV IGNOREHEADER 1 DATEFORMAT 'YYYY-MM-DD';

COPY dim_product FROM 's3://__STAGING_BUCKET__/stage/products/'
IAM_ROLE default FORMAT AS CSV IGNOREHEADER 1;

COPY stg_orders FROM 's3://__STAGING_BUCKET__/stage/orders/'
IAM_ROLE default FORMAT AS CSV IGNOREHEADER 1 GZIP TIMEFORMAT 'YYYY-MM-DD HH:MI:SS';

INSERT INTO fact_sales
SELECT order_id, TRUNC(order_ts), order_ts, customer_id, product_id, quantity,
       unit_price, discount, total_amount, channel, store_id, region, status
FROM stg_orders;

TRUNCATE stg_orders;

-- Check that every file was loaded and nothing was rejected
SELECT COUNT(*) AS fact_rows FROM fact_sales;
SELECT COUNT(*) AS load_errors FROM sys_load_error_detail;
