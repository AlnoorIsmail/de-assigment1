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
