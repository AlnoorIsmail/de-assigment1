"""Equivalent-work alternative to the historical benchmark in the notebook."""
from pathlib import Path
import re
import sqlite3


def pandas_assembly(database):
    import pandas as pd
    with sqlite3.connect(database) as connection:
        frames = {name: pd.read_sql(f'SELECT * FROM {name}', connection) for name in
                  ['orders', 'customers', 'order_items', 'products', 'category_translation', 'sellers', 'order_payments']}
    items = frames['order_items'].merge(frames['products'], on='product_id', how='left')
    items = items.merge(frames['category_translation'], on='product_category_name', how='left')
    items = items.merge(frames['sellers'], on='seller_id', how='left')
    items['resolved_category'] = items['product_category_name_english'].fillna(items['product_category_name']).fillna('unmapped')

    def sum_nullable(values):
        return values.sum(min_count=1)

    def max_text(values):
        return max(values.dropna(), default=None)

    def distinct_list(values):
        unique = values.dropna().unique()
        return ','.join(unique) if len(unique) else None

    item_summary = items.groupby('order_id').agg(
        total_items=('order_item_id', 'count'), basket_price=('price', sum_nullable),
        total_freight=('freight_value', sum_nullable), total_unique_sellers=('seller_id', 'nunique'),
        total_unique_seller_cities=('seller_city', 'nunique'), total_unique_seller_states=('seller_state', 'nunique'),
        seller_states_list=('seller_state', distinct_list), seller_cities_list=('seller_city', distinct_list),
        max_product_weight_g=('product_weight_g', 'max'), max_product_photos=('product_photos_qty', 'max'),
        selected_category=('resolved_category', max_text),
    ).reset_index()
    payment_summary = frames['order_payments'].groupby('order_id').agg(
        total_payment_value=('payment_value', sum_nullable), max_installments=('payment_installments', 'max'),
        selected_payment_type=('payment_type', max_text),
    ).reset_index()
    result = frames['orders'].merge(frames['customers'][['customer_id', 'customer_state', 'customer_city']], on='customer_id', how='left')
    result = result.merge(item_summary, on='order_id', how='left').merge(payment_summary, on='order_id', how='left')
    result['total_items'] = result['total_items'].fillna(0).astype(int)
    for column in ['basket_price', 'total_freight', 'max_product_photos', 'total_payment_value']:
        result[column] = result[column].fillna(0)

    def like_flag(row):
        states, customer = row['seller_states_list'], row['customer_state']
        if pd.isna(states) or pd.isna(customer):
            return 0
        pattern = '.*' + ''.join('.*' if char == '%' else '.' if char == '_' else re.escape(char) for char in customer) + '.*'
        return int(re.fullmatch(pattern, states, flags=re.IGNORECASE | re.ASCII | re.DOTALL) is not None)

    result['involves_local_seller'] = result.apply(like_flag, axis=1)
    columns = ['order_id', 'customer_id', 'order_status', 'order_purchase_timestamp', 'order_approved_at',
               'order_delivered_carrier_date', 'order_delivered_customer_date', 'order_estimated_delivery_date',
               'customer_state', 'customer_city', 'total_items', 'basket_price', 'total_freight',
               'total_unique_sellers', 'total_unique_seller_cities', 'total_unique_seller_states',
               'seller_states_list', 'seller_cities_list', 'max_product_weight_g', 'max_product_photos',
               'selected_category', 'involves_local_seller', 'total_payment_value', 'max_installments', 'selected_payment_type']
    return result[columns]


def sql_assembly(database, query):
    import pandas as pd
    with sqlite3.connect(database) as connection:
        return pd.read_sql(Path(query).read_text(), connection)


def assert_equivalent(left, right):
    import pandas as pd
    def canonical(frame):
        frame = frame.sort_values('order_id').reset_index(drop=True).copy()
        for column in ['seller_states_list', 'seller_cities_list']:
            # SQLite does not specify ordering inside GROUP_CONCAT(DISTINCT ...).
            frame[column] = frame[column].map(lambda value: ','.join(sorted(value.split(','))) if pd.notna(value) else value)
        return frame
    pd.testing.assert_frame_equal(canonical(left), canonical(right), check_dtype=False,
                                  check_exact=False, rtol=1e-12, atol=1e-9)
