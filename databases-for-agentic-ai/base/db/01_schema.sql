-- Riverbend Outfitters operational schema (shared by the missions). Re-runnable.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS commerce;
CREATE SCHEMA IF NOT EXISTS reporting;
CREATE SCHEMA IF NOT EXISTS bedrock_kb;

DROP VIEW IF EXISTS reporting.category_activity;
DROP VIEW IF EXISTS reporting.order_summary;
DROP TABLE IF EXISTS commerce.order_lines;
DROP TABLE IF EXISTS commerce.orders;
DROP TABLE IF EXISTS commerce.products;
DROP TABLE IF EXISTS commerce.customers;
DROP TABLE IF EXISTS commerce.audit_canary;

CREATE TABLE commerce.customers (
  customer_id   text PRIMARY KEY,
  full_name     text NOT NULL,
  email         text NOT NULL UNIQUE,
  phone         text NOT NULL,
  city          text NOT NULL,
  country       text NOT NULL,
  loyalty_tier  text NOT NULL,
  created_at    timestamptz NOT NULL
);

CREATE TABLE commerce.products (
  product_id    text PRIMARY KEY,
  product_name  text NOT NULL,
  category      text NOT NULL,
  unit_price    numeric(10,2) NOT NULL
);

CREATE TABLE commerce.orders (
  order_id      text PRIMARY KEY,
  customer_id   text NOT NULL REFERENCES commerce.customers,
  order_date    date NOT NULL,
  status        text NOT NULL,
  channel       text NOT NULL,
  total         numeric(12,2) NOT NULL DEFAULT 0
);
CREATE INDEX orders_customer_idx ON commerce.orders (customer_id);

CREATE TABLE commerce.order_lines (
  order_id      text NOT NULL REFERENCES commerce.orders,
  line_no       int  NOT NULL,
  product_id    text NOT NULL REFERENCES commerce.products,
  quantity      int  NOT NULL,
  unit_price    numeric(10,2) NOT NULL,
  PRIMARY KEY (order_id, line_no)
);

-- Rows the diagnostics mission uses to prove nothing can be modified.
CREATE TABLE commerce.audit_canary (id int PRIMARY KEY, note text NOT NULL);
