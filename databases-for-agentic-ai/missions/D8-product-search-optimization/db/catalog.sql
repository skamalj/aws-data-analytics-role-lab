-- Product catalog used by Trail Desk's product search tools (~200,000 products). Re-runnable:
-- each batch is skipped when its last product already exists.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS catalog;
CREATE TABLE IF NOT EXISTS catalog.products (
  product_id   text PRIMARY KEY,
  name         text NOT NULL,
  description  text NOT NULL,
  category     text NOT NULL,
  brand        text NOT NULL,
  price        numeric(10,2) NOT NULL,
  rating       numeric(2,1) NOT NULL,
  in_stock     boolean NOT NULL,
  embedding    vector(64) NOT NULL     -- product-similarity embedding from the catalog team
);
INSERT INTO catalog.products
SELECT 'X' || lpad(i::text, 6, '0'),
       b || ' ' || a || ' ' || t || ' ' || (100 + i % 900),
       'The ' || b || ' ' || t || ' is a ' || lower(a) || ' piece of ' || lower(c) || ' gear for ' ||
       (ARRAY['day hikes','alpine trips','wet weather','winter camping','long-distance trekking','climbing gyms'])[1 + i % 6] ||
       '. Features: ' || (ARRAY['waterproof membrane','recycled fabric','reinforced seams','ultralight frame','lifetime warranty','quick-dry lining'])[1 + (i * 7) % 6] ||
       ', ' || (ARRAY['reflective trims','adjustable fit','compression straps','vented panels','repairable design'])[1 + (i * 11) % 5] || '.',
       c, b,
       round((19 + (i * 7919) % 480)::numeric, 2),
       round((30 + (i * 13) % 21)::numeric / 10, 1),
       i % 9 <> 0,
       (SELECT array_agg(sin(i * 0.37 + d * 1.71) + cos(i * 0.013 * d))::vector FROM generate_series(1, 64) AS d)
FROM generate_series(1, 50000) AS i,
     LATERAL (SELECT (ARRAY['Kestrel','Summitline','Riverbend','Northpine','Talus','Cairn','Ember','Glacier'])[1 + (i / 7) % 8] AS b,
                     (ARRAY['Ultralight','Expedition','Trail','Storm','Alpine','Everyday','Pro','Classic'])[1 + (i / 61) % 8] AS a,
                     (ARRAY['Tent','Bivy','Boot','Runner','Jacket','Fleece','Pack','Vest','Stove','Pot Set','Harness','Rope'])[1 + (i * 5 + i / 97) % 12] AS t,
                     (ARRAY['Tents','Tents','Footwear','Footwear','Apparel','Apparel','Packs','Packs','Cooking','Cooking','Climbing','Climbing'])[1 + (i * 5 + i / 97) % 12] AS c) v
WHERE NOT EXISTS (SELECT 1 FROM catalog.products WHERE product_id = 'X050000');

INSERT INTO catalog.products
SELECT 'X' || lpad(i::text, 6, '0'),
       b || ' ' || a || ' ' || t || ' ' || (100 + i % 900),
       'The ' || b || ' ' || t || ' is a ' || lower(a) || ' piece of ' || lower(c) || ' gear for ' ||
       (ARRAY['day hikes','alpine trips','wet weather','winter camping','long-distance trekking','climbing gyms'])[1 + i % 6] ||
       '. Features: ' || (ARRAY['waterproof membrane','recycled fabric','reinforced seams','ultralight frame','lifetime warranty','quick-dry lining'])[1 + (i * 7) % 6] ||
       ', ' || (ARRAY['reflective trims','adjustable fit','compression straps','vented panels','repairable design'])[1 + (i * 11) % 5] || '.',
       c, b,
       round((19 + (i * 7919) % 480)::numeric, 2),
       round((30 + (i * 13) % 21)::numeric / 10, 1),
       i % 9 <> 0,
       (SELECT array_agg(sin(i * 0.37 + d * 1.71) + cos(i * 0.013 * d))::vector FROM generate_series(1, 64) AS d)
FROM generate_series(50001, 100000) AS i,
     LATERAL (SELECT (ARRAY['Kestrel','Summitline','Riverbend','Northpine','Talus','Cairn','Ember','Glacier'])[1 + (i / 7) % 8] AS b,
                     (ARRAY['Ultralight','Expedition','Trail','Storm','Alpine','Everyday','Pro','Classic'])[1 + (i / 61) % 8] AS a,
                     (ARRAY['Tent','Bivy','Boot','Runner','Jacket','Fleece','Pack','Vest','Stove','Pot Set','Harness','Rope'])[1 + (i * 5 + i / 97) % 12] AS t,
                     (ARRAY['Tents','Tents','Footwear','Footwear','Apparel','Apparel','Packs','Packs','Cooking','Cooking','Climbing','Climbing'])[1 + (i * 5 + i / 97) % 12] AS c) v
WHERE NOT EXISTS (SELECT 1 FROM catalog.products WHERE product_id = 'X100000');

INSERT INTO catalog.products
SELECT 'X' || lpad(i::text, 6, '0'),
       b || ' ' || a || ' ' || t || ' ' || (100 + i % 900),
       'The ' || b || ' ' || t || ' is a ' || lower(a) || ' piece of ' || lower(c) || ' gear for ' ||
       (ARRAY['day hikes','alpine trips','wet weather','winter camping','long-distance trekking','climbing gyms'])[1 + i % 6] ||
       '. Features: ' || (ARRAY['waterproof membrane','recycled fabric','reinforced seams','ultralight frame','lifetime warranty','quick-dry lining'])[1 + (i * 7) % 6] ||
       ', ' || (ARRAY['reflective trims','adjustable fit','compression straps','vented panels','repairable design'])[1 + (i * 11) % 5] || '.',
       c, b,
       round((19 + (i * 7919) % 480)::numeric, 2),
       round((30 + (i * 13) % 21)::numeric / 10, 1),
       i % 9 <> 0,
       (SELECT array_agg(sin(i * 0.37 + d * 1.71) + cos(i * 0.013 * d))::vector FROM generate_series(1, 64) AS d)
FROM generate_series(100001, 150000) AS i,
     LATERAL (SELECT (ARRAY['Kestrel','Summitline','Riverbend','Northpine','Talus','Cairn','Ember','Glacier'])[1 + (i / 7) % 8] AS b,
                     (ARRAY['Ultralight','Expedition','Trail','Storm','Alpine','Everyday','Pro','Classic'])[1 + (i / 61) % 8] AS a,
                     (ARRAY['Tent','Bivy','Boot','Runner','Jacket','Fleece','Pack','Vest','Stove','Pot Set','Harness','Rope'])[1 + (i * 5 + i / 97) % 12] AS t,
                     (ARRAY['Tents','Tents','Footwear','Footwear','Apparel','Apparel','Packs','Packs','Cooking','Cooking','Climbing','Climbing'])[1 + (i * 5 + i / 97) % 12] AS c) v
WHERE NOT EXISTS (SELECT 1 FROM catalog.products WHERE product_id = 'X150000');

INSERT INTO catalog.products
SELECT 'X' || lpad(i::text, 6, '0'),
       b || ' ' || a || ' ' || t || ' ' || (100 + i % 900),
       'The ' || b || ' ' || t || ' is a ' || lower(a) || ' piece of ' || lower(c) || ' gear for ' ||
       (ARRAY['day hikes','alpine trips','wet weather','winter camping','long-distance trekking','climbing gyms'])[1 + i % 6] ||
       '. Features: ' || (ARRAY['waterproof membrane','recycled fabric','reinforced seams','ultralight frame','lifetime warranty','quick-dry lining'])[1 + (i * 7) % 6] ||
       ', ' || (ARRAY['reflective trims','adjustable fit','compression straps','vented panels','repairable design'])[1 + (i * 11) % 5] || '.',
       c, b,
       round((19 + (i * 7919) % 480)::numeric, 2),
       round((30 + (i * 13) % 21)::numeric / 10, 1),
       i % 9 <> 0,
       (SELECT array_agg(sin(i * 0.37 + d * 1.71) + cos(i * 0.013 * d))::vector FROM generate_series(1, 64) AS d)
FROM generate_series(150001, 200000) AS i,
     LATERAL (SELECT (ARRAY['Kestrel','Summitline','Riverbend','Northpine','Talus','Cairn','Ember','Glacier'])[1 + (i / 7) % 8] AS b,
                     (ARRAY['Ultralight','Expedition','Trail','Storm','Alpine','Everyday','Pro','Classic'])[1 + (i / 61) % 8] AS a,
                     (ARRAY['Tent','Bivy','Boot','Runner','Jacket','Fleece','Pack','Vest','Stove','Pot Set','Harness','Rope'])[1 + (i * 5 + i / 97) % 12] AS t,
                     (ARRAY['Tents','Tents','Footwear','Footwear','Apparel','Apparel','Packs','Packs','Cooking','Cooking','Climbing','Climbing'])[1 + (i * 5 + i / 97) % 12] AS c) v
WHERE NOT EXISTS (SELECT 1 FROM catalog.products WHERE product_id = 'X200000');

GRANT USAGE ON SCHEMA catalog TO trail_desk_app;
GRANT SELECT ON catalog.products TO trail_desk_app;
ANALYZE catalog.products;
