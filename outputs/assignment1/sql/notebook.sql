SELECT name FROM sqlite_master WHERE type='table';
SELECT * FROM 'category_translation' LIMIT 2;
SELECT * FROM 'customers' LIMIT 2;
SELECT * FROM 'order_items' LIMIT 2;
SELECT * FROM 'order_payments' LIMIT 2;
SELECT * FROM 'order_reviews' LIMIT 2;
SELECT * FROM 'orders' LIMIT 2;
SELECT * FROM 'products' LIMIT 2;
SELECT * FROM 'sellers' LIMIT 2;
SELECT COUNT(*) FROM category_translation;
SELECT COUNT(*) FROM customers;
SELECT COUNT(*) FROM order_items;
SELECT COUNT(*) FROM order_payments;
SELECT COUNT(*) FROM order_reviews;
SELECT COUNT(*) FROM orders;
SELECT COUNT(*) FROM products;
SELECT COUNT(*) FROM sellers;
PRAGMA table_info("category_translation");
SELECT COUNT(*) FROM "category_translation";
SELECT * FROM "category_translation" LIMIT 2;
PRAGMA table_info("customers");
SELECT COUNT(*) FROM "customers";
SELECT * FROM "customers" LIMIT 2;
PRAGMA table_info("order_items");
SELECT COUNT(*) FROM "order_items";
SELECT * FROM "order_items" LIMIT 2;
PRAGMA table_info("order_payments");
SELECT COUNT(*) FROM "order_payments";
SELECT * FROM "order_payments" LIMIT 2;
PRAGMA table_info("order_reviews");
SELECT COUNT(*) FROM "order_reviews";
SELECT * FROM "order_reviews" LIMIT 2;
PRAGMA table_info("orders");
SELECT COUNT(*) FROM "orders";
SELECT * FROM "orders" LIMIT 2;
PRAGMA table_info("products");
SELECT COUNT(*) FROM "products";
SELECT * FROM "products" LIMIT 2;
PRAGMA table_info("sellers");
SELECT COUNT(*) FROM "sellers";
SELECT * FROM "sellers" LIMIT 2;

        SELECT 
            COUNT(DISTINCT order_id) AS total_orders,
            CAST(COUNT(*) AS REAL) / COUNT(DISTINCT order_id) AS avg_items_per_order
        FROM order_items;

        SELECT 
            COUNT(DISTINCT order_id) AS total_orders_with_payments,
            CAST(COUNT(*) AS REAL) / COUNT(DISTINCT order_id) AS avg_payments_per_order
        FROM order_payments;
SELECT COUNT(*) FROM orders;
SELECT COUNT(*) AS item_count, SUM(price) AS price_sum, SUM(freight_value) AS freight_sum FROM order_items;
SELECT COUNT(*) FROM orders WHERE order_id IS NULL;
SELECT COUNT(order_id) - COUNT(DISTINCT order_id) FROM orders;
SELECT COUNT(*) FROM customers WHERE customer_id IS NULL;
SELECT COUNT(customer_id) - COUNT(DISTINCT customer_id) FROM customers;
SELECT COUNT(product_id) - COUNT(DISTINCT product_id) FROM products;
SELECT COUNT(seller_id) - COUNT(DISTINCT seller_id) FROM sellers;

        SELECT COUNT(*) FROM (SELECT 1 FROM order_items
                              GROUP BY order_id, order_item_id HAVING COUNT(*) > 1);
SELECT COUNT(*) FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.customer_id WHERE c.customer_id IS NULL;
SELECT COUNT(*) FROM order_items oi
        LEFT JOIN orders o ON oi.order_id = o.order_id WHERE o.order_id IS NULL;
SELECT COUNT(*) FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.product_id WHERE p.product_id IS NULL;
SELECT COUNT(*) FROM order_items oi
        LEFT JOIN sellers s ON oi.seller_id = s.seller_id WHERE s.seller_id IS NULL;
SELECT COUNT(*) FROM order_payments op
        LEFT JOIN orders o ON op.order_id = o.order_id WHERE o.order_id IS NULL;
SELECT COUNT(*) FROM order_reviews r
        LEFT JOIN orders o ON r.order_id = o.order_id WHERE o.order_id IS NULL;
SELECT COUNT(*) FROM customers c
        LEFT JOIN orders o ON c.customer_id = o.customer_id WHERE o.order_id IS NULL;
SELECT COUNT(*) FROM products p
        LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name
        WHERE p.product_category_name IS NOT NULL AND ct.product_category_name IS NULL;
SELECT o.customer_id AS k FROM orders o LEFT JOIN customers c
                               ON o.customer_id = c.customer_id WHERE c.customer_id IS NULL;
SELECT customer_id AS k FROM customers;
SELECT oi.product_id AS k FROM order_items oi LEFT JOIN products p
                                   ON oi.product_id = p.product_id WHERE p.product_id IS NULL;
SELECT product_id AS k FROM products;
SELECT oi.seller_id AS k FROM order_items oi LEFT JOIN sellers s
                                  ON oi.seller_id = s.seller_id WHERE s.seller_id IS NULL;
SELECT seller_id AS k FROM sellers;

    WITH item_summary AS (
        SELECT 
            oi.order_id,
            COUNT(oi.order_item_id) AS total_items,
            SUM(oi.price) AS basket_price,
            SUM(oi.freight_value) AS total_freight,
            COUNT(DISTINCT oi.seller_id) AS total_unique_sellers,
            COUNT(DISTINCT s.seller_city) AS total_unique_seller_cities,
            COUNT(DISTINCT s.seller_state) AS total_unique_seller_states,
            GROUP_CONCAT(DISTINCT s.seller_state) AS seller_states_list,
            GROUP_CONCAT(DISTINCT s.seller_city) AS seller_cities_list,
            MAX(p.product_weight_g) AS max_product_weight_g,
            MAX(p.product_photos_qty) AS max_product_photos,
            MAX(COALESCE(ct.product_category_name_english, p.product_category_name, 'unmapped')) AS selected_category
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.product_id
        LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name
        LEFT JOIN sellers s ON oi.seller_id = s.seller_id
        GROUP BY oi.order_id
    ),
    payment_summary AS (
        SELECT 
            order_id,
            SUM(payment_value) AS total_payment_value,
            MAX(payment_installments) AS max_installments,
            MAX(payment_type) AS selected_payment_type
        FROM order_payments
        GROUP BY order_id
    )
    SELECT 
        o.order_id,
        o.customer_id,
        o.order_status,
        o.order_purchase_timestamp,
        o.order_approved_at,
        o.order_delivered_carrier_date,
        o.order_delivered_customer_date,
        o.order_estimated_delivery_date,
        c.customer_state,
        c.customer_city,
        COALESCE(i.total_items, 0) AS total_items,
        COALESCE(i.basket_price, 0.0) AS basket_price,
        COALESCE(i.total_freight, 0.0) AS total_freight,
        i.total_unique_sellers,
        i.total_unique_seller_cities,
        i.total_unique_seller_states,
        i.seller_states_list,
        i.seller_cities_list,
        i.max_product_weight_g,
        COALESCE(i.max_product_photos, 0) AS max_product_photos,
        i.selected_category,
        -- Provisional flag on uncleaned text; recomputed correctly in section 2.5
        CASE WHEN i.seller_states_list LIKE '%' || c.customer_state || '%' THEN 1 ELSE 0 END AS involves_local_seller,
        COALESCE(p.total_payment_value, 0.0) AS total_payment_value,
        p.max_installments,
        p.selected_payment_type
    FROM orders o
    LEFT JOIN customers c ON o.customer_id = c.customer_id
    LEFT JOIN item_summary i ON o.order_id = i.order_id
    LEFT JOIN payment_summary p ON o.order_id = p.order_id;
SELECT * FROM orders;
SELECT * FROM customers;
SELECT * FROM order_items;
SELECT * FROM products;
SELECT * FROM category_translation;
SELECT * FROM sellers;
SELECT * FROM order_payments;

    WITH item_summary AS (
        SELECT 
            oi.order_id,
            COUNT(oi.order_item_id) AS total_items,
            SUM(oi.price) AS basket_price,
            SUM(oi.freight_value) AS total_freight,
            COUNT(DISTINCT oi.seller_id) AS total_unique_sellers,
            COUNT(DISTINCT s.seller_city) AS total_unique_seller_cities,
            COUNT(DISTINCT s.seller_state) AS total_unique_seller_states,
            GROUP_CONCAT(DISTINCT s.seller_state) AS seller_states_list,
            GROUP_CONCAT(DISTINCT s.seller_city) AS seller_cities_list,
            MAX(p.product_weight_g) AS max_product_weight_g,
            MAX(p.product_photos_qty) AS max_product_photos,
            MAX(COALESCE(ct.product_category_name_english, p.product_category_name, 'unmapped')) AS selected_category
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.product_id
        LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name
        LEFT JOIN sellers s ON oi.seller_id = s.seller_id
        GROUP BY oi.order_id
    ),
    payment_summary AS (
        SELECT 
            order_id,
            SUM(payment_value) AS total_payment_value,
            MAX(payment_installments) AS max_installments,
            MAX(payment_type) AS selected_payment_type
        FROM order_payments
        GROUP BY order_id
    )
    SELECT 
        o.order_id,
        o.customer_id,
        o.order_status,
        o.order_purchase_timestamp,
        o.order_approved_at,
        o.order_delivered_carrier_date,
        o.order_delivered_customer_date,
        o.order_estimated_delivery_date,
        c.customer_state,
        c.customer_city,
        COALESCE(i.total_items, 0) AS total_items,
        COALESCE(i.basket_price, 0.0) AS basket_price,
        COALESCE(i.total_freight, 0.0) AS total_freight,
        i.total_unique_sellers,
        i.total_unique_seller_cities,
        i.total_unique_seller_states,
        i.seller_states_list,
        i.seller_cities_list,
        i.max_product_weight_g,
        COALESCE(i.max_product_photos, 0) AS max_product_photos,
        i.selected_category,
        -- Provisional flag on uncleaned text; recomputed correctly in section 2.5
        CASE WHEN i.seller_states_list LIKE '%' || c.customer_state || '%' THEN 1 ELSE 0 END AS involves_local_seller,
        COALESCE(p.total_payment_value, 0.0) AS total_payment_value,
        p.max_installments,
        p.selected_payment_type
    FROM orders o
    LEFT JOIN customers c ON o.customer_id = c.customer_id
    LEFT JOIN item_summary i ON o.order_id = i.order_id
    LEFT JOIN payment_summary p ON o.order_id = p.order_id;

        SELECT order_id, price, freight_value 
        FROM order_items 
        WHERE price < 0 OR freight_value < 0 
        LIMIT 5;

        SELECT oi.order_id, oi.price, oi.freight_value, p.product_weight_g, p.product_photos_qty
        FROM order_items oi LEFT JOIN products p ON oi.product_id = p.product_id;

        SELECT oi.order_id, oi.order_item_id, oi.product_id, oi.seller_id,
               oi.price, oi.freight_value, p.product_weight_g,
               p.product_photos_qty, s.seller_state
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.product_id
        LEFT JOIN sellers s ON oi.seller_id = s.seller_id
    ;
