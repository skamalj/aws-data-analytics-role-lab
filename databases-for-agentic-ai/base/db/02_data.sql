-- Deterministic sample data (no random(): every learner gets identical numbers).
INSERT INTO commerce.products (product_id, product_name, category, unit_price) VALUES
 ('P101','Trailhead 2P Tent','Tents',189.00), ('P102','Summit 4P Tent','Tents',349.00), ('P103','Bivy Shelter','Tents',129.00),
 ('P104','Ridge Hiking Boot','Footwear',159.00), ('P105','Trail Runner','Footwear',119.00), ('P106','Camp Sandal','Footwear',49.00),
 ('P107','Rain Shell Jacket','Apparel',139.00), ('P108','Merino Base Layer','Apparel',79.00), ('P109','Fleece Hoodie','Apparel',69.00),
 ('P110','Daypack 22L','Packs',89.00), ('P111','Expedition Pack 65L','Packs',259.00), ('P112','Hydration Vest','Packs',99.00),
 ('P113','Ultralight Stove','Cooking',59.00), ('P114','Titanium Pot Set','Cooking',74.00), ('P115','Water Filter','Cooking',44.00),
 ('P116','Harness','Climbing',64.00), ('P117','Dynamic Rope 60m','Climbing',219.00), ('P118','Chalk Bag','Climbing',19.00);

INSERT INTO commerce.customers
SELECT 'C' || lpad(i::text, 5, '0'),
       (ARRAY['Ana','Ben','Chen','Dara','Eli','Fatima','Gus','Hana','Ivan','Jo','Kofi','Lena','Mateo','Nia','Omar','Priya'])[1 + i % 16]
         || ' ' ||
       (ARRAY['Alvarez','Berg','Costa','Dubois','Evans','Fischer','Gupta','Hughes','Ito','Jensen','Kim'])[1 + (i * 7) % 11],
       'customer' || i || '@example.com',
       '+1-555-' || lpad(((i * 7919) % 10000)::text, 4, '0'),
       (ARRAY['Seattle','Lyon','Pune','Denver','Dublin','Sydney','Lima','Osaka'])[1 + (i * 3) % 8],
       (ARRAY['US','FR','IN','US','IE','AU','PE','JP'])[1 + (i * 3) % 8],
       (ARRAY['bronze','bronze','bronze','silver','silver','gold','platinum'])[1 + (i * 5) % 7],
       timestamptz '2024-01-01' + ((i * 17) % 700) * interval '1 day'
FROM generate_series(1, 500) AS i;

INSERT INTO commerce.orders (order_id, customer_id, order_date, status, channel)
SELECT 'O' || (1000 + i),
       'C' || lpad((1 + (i * 37) % 500)::text, 5, '0'),
       date '2026-01-01' + (i * 13) % 300,
       CASE WHEN i % 20 = 0 THEN 'CANCELLED' WHEN i % 20 IN (1, 2) THEN 'RETURNED'
            WHEN i % 20 = 3 THEN 'SHIPPED' ELSE 'DELIVERED' END,
       (ARRAY['web','store','mobile'])[1 + i % 3]
FROM generate_series(1, 5000) AS i;

INSERT INTO commerce.order_lines (order_id, line_no, product_id, quantity, unit_price)
SELECT o.order_id, l, p.product_id, 1 + (n + l) % 3, p.unit_price
FROM (SELECT order_id, (substr(order_id, 2)::int - 1000) AS n FROM commerce.orders) o
CROSS JOIN LATERAL generate_series(1, 1 + o.n % 3) AS l
JOIN commerce.products p ON p.product_id = 'P' || (101 + (o.n * 7 + l) % 18);

UPDATE commerce.orders o SET total = s.t
FROM (SELECT order_id, sum(quantity * unit_price) AS t FROM commerce.order_lines GROUP BY order_id) s
WHERE s.order_id = o.order_id;

INSERT INTO commerce.audit_canary VALUES (1, 'If this row is ever changed or deleted, a tool had write access it should not have.');

-- Curated, agent-facing views (the only objects agent tools are meant to read).
CREATE VIEW reporting.order_summary AS
SELECT o.order_id, o.customer_id, o.order_date, o.status, o.channel, o.total,
       count(l.line_no) AS lines, string_agg(p.product_name, ', ' ORDER BY l.line_no) AS items
FROM commerce.orders o
JOIN commerce.order_lines l ON l.order_id = o.order_id
JOIN commerce.products p ON p.product_id = l.product_id
GROUP BY o.order_id;

CREATE VIEW reporting.category_activity AS
SELECT p.category,
       count(*)                AS order_line_count,
       sum(l.quantity)         AS units_sold,
       max(o.order_date)       AS latest_activity
FROM commerce.order_lines l
JOIN commerce.orders o   ON o.order_id = l.order_id
JOIN commerce.products p ON p.product_id = l.product_id
WHERE o.status <> 'CANCELLED'
GROUP BY p.category;
