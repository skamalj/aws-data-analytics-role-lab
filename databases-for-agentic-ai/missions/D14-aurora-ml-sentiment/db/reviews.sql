-- Customer reviews for the "customer intelligence" questions (600 reviews over the 18 products). Re-runnable.
CREATE TABLE IF NOT EXISTS commerce.reviews (
  review_id    int PRIMARY KEY,
  product_id   text NOT NULL REFERENCES commerce.products,
  customer_id  text NOT NULL REFERENCES commerce.customers,
  stars        int  NOT NULL,
  review_text  text NOT NULL,
  created_at   date NOT NULL
);
INSERT INTO commerce.reviews
SELECT i, 'P' || (101 + (i * 7) % 18), 'C' || lpad((1 + (i * 37) % 500)::text, 5, '0'),
       CASE WHEN i % 5 IN (0, 1, 2) THEN 5 WHEN i % 5 = 3 THEN 3 ELSE 1 END,
       CASE WHEN i % 5 IN (0, 1, 2) THEN
              (ARRAY['Absolutely love it, great quality and it kept me dry all weekend.',
                     'Fantastic gear, comfortable and well made. Highly recommend!',
                     'Excellent value, works perfectly on long hikes. Very happy.'])[1 + i % 3]
            WHEN i % 5 = 3 THEN
              (ARRAY['It is okay. Does the job, nothing special.',
                     'Average product, arrived on time.'])[1 + i % 2]
            ELSE
              (ARRAY['Terrible. It broke after two trips and support never answered.',
                     'Very disappointed, the seams leaked on the first rainy day.',
                     'Poor quality and uncomfortable, I returned it.'])[1 + i % 3] END,
       date '2026-01-01' + (i * 11) % 300
FROM generate_series(1, 600) AS i
ON CONFLICT (review_id) DO NOTHING;

-- Aurora machine learning: SQL functions that call Amazon Comprehend (aws_comprehend.detect_sentiment)
-- are provided by the aws_ml extension. (Aurora only - not available in community PostgreSQL.)
