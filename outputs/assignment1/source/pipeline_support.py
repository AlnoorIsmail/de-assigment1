"""Stage definitions, lossless CSV exports, and observers for the notebook."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import threading
import time

OWNER = 'eng2040-assignment1-pipeline-v1'
NULL = r'\N'
STAGES = [
    ('01_setup', 'Library setup', ['da38f79a', '7353867d'], []),
    ('02_inspection', 'Database inspection', ['d4265e67', '0214ead5'], ['00_database']),
    ('03_multiplicity', 'Item and payment multiplicity', ['d5549e0c'], ['00_database']),
    ('04_preservation', 'Record and value preservation', ['718846ea', 'e5cec750'], ['00_database']),
    ('05_assembly', 'Order-level assembly', ['c80b09ce', '2cc6c7aa'], ['00_database']),
    ('06_original_benchmark', 'Equivalent notebook benchmark', ['106000f2'], ['00_database']),
    ('07_profile', 'Quality profiling and source verification',
     ['ed413ece', '18544014', 'ededf2f3', 'c33b80d1', '0dbf5ac7', '99ab5fa0', '5d75ffcc', 'timestamp-audit'], ['05_assembly']),
    ('08_cleaning', 'Cleaning, labeling, and exclusion audit', ['8665d277'], ['05_assembly', '07_profile']),
    ('09_eda_delivery', 'Delivery frequency and duration', ['8514d605'], ['08_cleaning']),
    ('10_eda_window', 'Promised window and distributions', ['fc6afe81'], ['09_eda_delivery']),
    ('11_eda_state', 'Customer-state performance', ['7bbaf20a'], ['10_eda_window']),
    ('12_eda_hypotheses', 'Photos, payments, and local fulfillment', ['3aedf5bf'], ['10_eda_window']),
    ('13_eda_weight', 'Weight and delay duration', ['c9855097'], ['10_eda_window']),
    ('14_eda_sellers', 'Seller complexity and comparison summary', ['9e6eada0'], ['12_eda_hypotheses']),
    ('15_initial_features', 'Approval-time features and state encoding', ['a57ab7fa'], ['10_eda_window']),
    ('16_final_features', 'Final features, labels and IDs', ['ba4e672f'], ['15_initial_features']),
    ('17_resources', 'Notebook resource summary', ['resource-summary'], ['16_final_features']),
]


def dump_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def directory_bytes(path):
    total = 0
    for item in Path(path).rglob('*'):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
        except FileNotFoundError:
            pass
    return total


class ResourceMeter:
    """Sample this process's RSS and visible scratch/journal files, in bytes."""

    def __init__(self, temporary, database=None):
        import psutil
        self.process = psutil.Process()
        self.temporary = Path(temporary)
        self.database = Path(database) if database else None
        self.interval = 0.01
        self.stop_event = threading.Event()
        self.peak_rss = self.start_rss = self.process.memory_info().rss
        self.peak_temp = 0
        self.samples = 0
        self.sampling_seconds = 0.0
        self.max_gap_seconds = 0.0
        self.previous_sample = None

    def sample(self):
        started = time.perf_counter()
        if self.previous_sample is not None:
            self.max_gap_seconds = max(self.max_gap_seconds, started - self.previous_sample)
        self.previous_sample = started
        self.peak_rss = max(self.peak_rss, self.process.memory_info().rss)
        temporary = directory_bytes(self.temporary)
        if self.database:
            for suffix in ['-journal', '-wal', '-shm']:
                try:
                    temporary += Path(str(self.database) + suffix).stat().st_size
                except FileNotFoundError:
                    pass
        self.peak_temp = max(self.peak_temp, temporary)
        self.samples += 1
        self.sampling_seconds += time.perf_counter() - started

    def loop(self):
        while not self.stop_event.wait(self.interval):
            self.sample()

    def start(self):
        self.sample()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.started = time.perf_counter()
        self.thread.start()
        return self

    def stop(self):
        elapsed = time.perf_counter() - self.started
        self.stop_event.set()
        self.thread.join()
        self.sample()
        return {
            'elapsed_seconds': elapsed,
            'start_rss_bytes': self.start_rss,
            'peak_rss_bytes': self.peak_rss,
            'peak_rss_increase_bytes': self.peak_rss - self.start_rss,
            'peak_temporary_bytes': self.peak_temp,
            'sampling_overhead_seconds': self.sampling_seconds,
            'sample_interval_seconds': self.interval,
            'maximum_sample_gap_seconds': self.max_gap_seconds,
            'samples': self.samples,
        }


def stage_bindings(stage, ns, database):
    """Yield (filename, dataframe, row meaning, projection scale) without mutating data."""
    import pandas as pd
    def bind(name, meaning, scale='orders', filename=None):
        value = ns[name]
        if isinstance(value, pd.Series):
            value = value.to_frame()
        return (filename or name, value, meaning, scale)

    if stage == '02_inspection':
        with sqlite3.connect(database) as conn:
            overview, schema, samples = [], [], []
            for table in ns['tables']:
                quoted = '"' + table.replace('"', '""') + '"'
                info = pd.read_sql(f'PRAGMA table_info({quoted})', conn)
                info.insert(0, 'table_name', table)
                schema.append(info)
                count = conn.execute(f'SELECT COUNT(*) FROM {quoted}').fetchone()[0]
                overview.append({'table_name': table, 'rows': count})
                samples.append((f'sample_{table}', pd.read_sql(f'SELECT * FROM {quoted} LIMIT 2', conn),
                                f'One sampled source record from {table}', 'fixed'))
        yield 'table_overview', pd.DataFrame(overview), 'One source table', 'fixed'
        yield 'schema', pd.concat(schema, ignore_index=True), 'One source column', 'fixed'
        yield from samples
    elif stage == '03_multiplicity':
        for name in ['item_counts', 'payment_counts']:
            yield bind(name, 'One multiplicity summary', 'fixed')
    elif stage == '04_preservation':
        # Source baselines are recorded here; they are compared with the actual SQL assembly in 05.
        totals = ns['source_totals']
        yield 'source_baselines', pd.DataFrame([{
            'source_orders': int(ns['source_order_count']), 'source_item_rows': int(totals['item_count']),
            'source_price_sum': float(totals['price_sum']), 'source_freight_sum': float(totals['freight_sum'])}]), \
            'One set of source totals recorded before assembly', 'fixed'
        yield bind('key_audit', 'One source key-integrity check', 'fixed')
        yield bind('orphan_recovery', 'One attempted orphan-key recovery check', 'fixed')
    elif stage == '05_assembly':
        yield bind('master_orders', 'One original order with aggregated child records')
        raw, totals = ns['master_orders'], ns['source_totals']
        yield 'preservation', pd.DataFrame([
            {'measure': 'orders', 'source': int(ns['source_order_count']), 'assembled': len(raw)},
            {'measure': 'item_rows', 'source': int(totals['item_count']), 'assembled': int(raw['total_items'].sum())},
            {'measure': 'price_sum', 'source': float(totals['price_sum']), 'assembled': float(raw['basket_price'].sum())},
            {'measure': 'freight_sum', 'source': float(totals['freight_sum']), 'assembled': float(raw['total_freight'].sum())},
        ]), 'One preserved measure: source total versus the actual SQL assembly', 'fixed'
    elif stage == '06_original_benchmark':
        for name in ['master_memory', 'master_pushdown']:
            yield bind(name, 'One order in the equivalent-work benchmark')
        yield 'measurements', pd.DataFrame([
            {'approach': 'pandas', 'seconds': ns['duration_mem'], 'traced_peak_bytes': ns['peak_mem_bytes']},
            {'approach': 'sql', 'seconds': ns['duration_push'], 'traced_peak_bytes': ns['peak_push_bytes']},
        ]), 'One equivalent benchmark approach; traced Python memory and timings vary', 'fixed'
    elif stage == '07_profile':
        for name, meaning in [('anomaly_df', 'One numerical anomaly check'),
                              ('check_negatives', 'One raw item with a negative amount, up to five'),
                              ('text_audit_df', 'One profiled text column'),
                              ('date_null_df', 'One profiled timestamp column')]:
            yield bind(name, meaning, 'fixed')
        yield bind('outlier_df', 'One source-variable outlier profile', 'fixed')
        yield bind('date_parse_audit', 'One timestamp parse audit', 'fixed')
        yield 'status_of_missing', ns['status_of_missing'].rename('count').reset_index(), 'One order status with missing delivery dates', 'fixed'
    elif stage == '08_cleaning':
        yield bind('df_clean', 'One original order after cleaning, including unlabeled outcomes')
        yield bind('df_labeled', 'One retained order with a delivery label')
        yield bind('audit_df', 'One delivery-label checkpoint', 'fixed')
        yield bind('feature_audit_df', 'One feature-eligibility checkpoint', 'fixed')
        yield bind('item_repair_audit', 'One amount type with invalid, imputed and unresolved item counts', 'fixed')
        yield bind('source_items', 'One source item with cleaning flags and cleaned optional attributes')
        yield 'clean_item_summary', ns['clean_item_summary'].reset_index(), 'One order with cleaned item aggregates', 'orders'
        yield bind('sensitivity_df', 'One inclusion policy and its delivery outcomes', 'fixed')
        yield bind('state_sensitivity', 'One inclusion policy and customer-state group', 'fixed')
        raw = ns['master_orders']
        audit = raw[['order_id']].copy()
        masks = {key: ns[key] for key in [
            'anomaly_mask', 'chronology_mask', 'missing_outcome_mask', 'unknown_status_mask',
            'exclusion_mask', 'no_items_mask', 'unresolved_amount_mask', 'feature_eligible_mask']}
        # Same definition as before: an impossible event order or a missing outcome date.
        masks['contradiction_mask'] = masks['chronology_mask'] | masks['missing_outcome_mask']
        for key in ['anomaly_mask', 'chronology_mask', 'missing_outcome_mask',
                    'unknown_status_mask', 'contradiction_mask', 'exclusion_mask',
                    'no_items_mask', 'unresolved_amount_mask', 'feature_eligible_mask']:
            audit[key] = masks[key].reindex(raw.index, fill_value=False).astype(bool)
        audit['retained_clean_record'] = raw.index.isin(ns['df_clean'].index)
        audit['retained_with_label'] = raw.index.isin(ns['df_labeled'].index)
        audit['unlabelled'] = ~audit['retained_with_label']
        audit[['exclusion_reason', 'feature_exclusion_reason']] = ns['df_clean'][['exclusion_reason', 'feature_exclusion_reason']]
        yield 'order_audit', audit, 'One source order with the original masks and retention decisions', 'orders'
    elif stage == '09_eda_delivery':
        yield bind('df_labeled', 'One labeled order with computed delay days')
        yield 'delivery_summary', pd.DataFrame([{key: ns[key] for key in
            ['total_orders', 'late_count', 'late_pct', 'rate_lo', 'rate_hi', 'delay_median', 'delay_q1', 'delay_q3', 'mean_lo', 'mean_hi', 'q99', 'n_tail']}]), 'Overall late rate with its 95% Wilson interval, and delay median, IQR and mean with its 95% CI', 'fixed'
        yield 'delay_band_table', ns['delay_band_table'].rename_axis('Delay band').reset_index(), 'One late-delivery severity band', 'fixed'
        yield 'chart_01_outcomes', ns['df_labeled'][['order_id', ns['target_col']]], 'One labeled order used by the count plot', 'orders'
        yield 'chart_02_delays', ns['late_orders_df'][['order_id', 'delay_days']], 'One late order used by the delay histogram', 'orders'
        counts = ns['df_labeled'][ns['target_col']].value_counts().sort_index().rename('count').reset_index()
        yield 'outcome_counts', counts, 'One delivery outcome', 'fixed'
        stats = ns['late_orders_df']['delay_days'].describe(percentiles=[.25, .5, .75, .90, .95])
        yield 'delay_statistics', stats.rename('days').rename_axis('statistic').reset_index(), 'One delay-duration statistic', 'fixed'
    elif stage == '10_eda_window':
        yield bind('df_labeled', 'One labeled order with delay and promised-window features')
        yield bind('window_comparison', 'The 0-7 day window against longer windows, compared by 95% Wilson intervals', 'fixed')
        yield bind('window_summary', 'One delivery outcome', 'fixed')
        yield bind('window_rates', 'One approval-to-estimate calendar-day band', 'fixed')
        yield 'chart_01_window', ns['df_labeled'][['order_id', ns['target_col'], 'promised_window_days']], 'One order used by the window box plot', 'orders'
        yield 'chart_02_distributions', ns['df_labeled'][['order_id', 'basket_price_repaired', 'max_product_weight_g']], 'One order used by the two feature histograms', 'orders'
    elif stage == '11_eda_state':
        for name in ['state_perf', 'state_perf_filtered', 'top_problem_states']:
            yield bind(name, 'One customer state', 'fixed')
    elif stage == '12_eda_hypotheses':
        for name, meaning in [('photo_grouped', 'One maximum photo-count group'),
                              ('payment_grouped', 'One alphabetically selected payment type'),
                              ('local_grouped', 'One fulfillment group')]:
            yield bind(name, meaning, 'fixed')
        yield bind('local_comparison', 'Cross-state against local fulfilment, compared by 95% Wilson intervals', 'fixed')
        yield bind('photo_band_rates', 'One photo band and reliable delivery outcomes', 'fixed')
        yield bind('nondelivery_rates', 'One photo band and all-order status outcomes', 'fixed')
        photos = ns['photo_grouped']
        yield 'chart_01_photos', photos[photos['max_product_photos'] <= 10], 'One photo-count group displayed in the chart', 'fixed'
    elif stage == '13_eda_weight':
        yield 'scatter_df', ns['scatter_df'][['order_id', 'max_product_weight_g', 'delay_days']], 'One late order with a recorded product weight', 'orders'
    elif stage == '14_eda_sellers':
        yield bind('comparison_summary', 'One Part 3 comparison and its interval-based finding', 'fixed')
        yield bind('seller_comparison', 'Two-seller against one-seller orders, compared by 95% Wilson intervals', 'fixed')
        for name in ['seller_analysis', 'state_seller_analysis']:
            yield bind(name, 'One seller-count or seller-state-count group', 'fixed')
    elif stage == '17_resources':
        yield bind('resource_df', 'One measured notebook step; runtime seconds and peak traced MiB', 'fixed')
        yield bind('object_sizes', 'One retained object and its deep memory size', 'fixed')
    elif stage in ['15_initial_features', '16_final_features']:
        frame = 'df_features' if stage == '15_initial_features' else 'df_pipeline'
        yield bind(frame, 'One feature-eligible order with engineered columns')
        for name in (['df_encoded'] if stage == '15_initial_features' else ['X_numeric', 'X_categorical']):
            yield bind(name, 'One feature-eligible order; row-aligned with order_ids')
        if stage == '16_final_features':
            # The feature matrix, labels and IDs are built once, in the final step.
            for name in ['X', 'y', 'order_ids']:
                yield bind(name, 'One feature-eligible order; X, y, and order_ids are aligned by row position')
            yield bind('X_unfilled', 'One feature-eligible order before full-dataset median imputation')
            yield bind('imputation_values', 'One feature and its full-dataset imputation value', 'fixed')



CHART_DATA = {
    '09_eda_delivery': [['chart_01_outcomes'], ['chart_02_delays']],
    '10_eda_window': [['chart_01_window'], ['window_rates'], ['chart_02_distributions']],
    '11_eda_state': [['top_problem_states']],
    '12_eda_hypotheses': [['chart_01_photos'], ['payment_grouped'], ['local_grouped']],
    '13_eda_weight': [['scatter_df']],
    '14_eda_sellers': [['seller_analysis']],
}


def write_frame(root, stage, name, frame, meaning, scale):
    import pandas as pd
    folder = Path(root) / 'stages' / stage
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{name}.csv'
    encoded = frame.copy()
    columns = []
    for column in frame.columns:
        series = frame[column]
        encoding = 'scalar'
        if series.dtype == object and series.dropna().map(lambda x: isinstance(x, (list, dict, tuple))).any():
            encoding = 'json'
            encoded[column] = series.map(lambda x: json.dumps(x, ensure_ascii=False, allow_nan=False))
        elif pd.api.types.is_datetime64_any_dtype(series):
            encoding = 'datetime'
        if encoded[column].dropna().astype(str).eq(NULL).any():
            raise ValueError(f'{path}: literal {NULL!r} collides with the CSV null marker')
        columns.append({'name': column, 'dtype': str(series.dtype), 'encoding': encoding,
                        'nullable': bool(series.isna().any())})
    encoded.to_csv(path, index=False, na_rep=NULL, lineterminator='\n')
    schema = {'columns': columns, 'null_marker': NULL, 'index_saved': False,
              'row_meaning': meaning, 'row_order': 'unchanged from notebook'}
    schema_path = path.with_suffix('.schema.json')
    dump_json(schema_path, schema)
    return {'path': str(path.relative_to(root)), 'schema': str(schema_path.relative_to(root)),
            'stage': stage, 'name': name, 'rows': len(frame), 'columns': len(frame.columns),
            'row_meaning': meaning, 'projection_scale': scale,
            'logical_memory_bytes': int(frame.memory_usage(index=True, deep=True).sum()),
            'bytes': path.stat().st_size, 'schema_bytes': schema_path.stat().st_size,
            'sha256': sha256(path), 'deterministic': name not in ['measurements', 'resource_df', 'object_sizes']}


def read_frame(path):
    """Load an exported CSV using its schema; no automatic NA or ID inference."""
    import pandas as pd
    path = Path(path)
    schema = json.loads(path.with_suffix('.schema.json').read_text())
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[schema['null_marker']],
                        float_precision='round_trip')
    for column in schema['columns']:
        name, dtype, encoding = column['name'], column['dtype'], column['encoding']
        if encoding == 'json':
            frame[name] = frame[name].map(json.loads)
        elif encoding == 'datetime':
            frame[name] = pd.to_datetime(frame[name]).astype(dtype)
        elif dtype in ['bool', 'boolean']:
            frame[name] = frame[name].map({'True': True, 'False': False}).astype(dtype)
        else:
            frame[name] = frame[name].astype(dtype)
    return frame


def validate_results(ns):
    import numpy as np
    import pandas as pd
    raw, labeled, features = ns['master_orders'], ns['df_labeled'], ns['X']
    assert raw['order_id'].is_unique
    totals = ns['source_totals']
    assert len(raw) == ns['source_order_count']
    assert raw['total_items'].sum() == totals['item_count']
    assert abs(raw['basket_price'].sum() - totals['price_sum']) < 1e-2
    assert abs(raw['total_freight'].sum() - totals['freight_sum']) < 1e-2
    assert labeled['order_id'].is_unique
    assert set(ns['y'].unique()) <= {0, 1}
    assert features.index.equals(ns['y'].index) and features.index.equals(ns['order_ids'].index)
    assert all(pd.api.types.is_numeric_dtype(dtype) for dtype in features.dtypes)
    assert np.isfinite(features.to_numpy()).all()
    assert len(ns['df_clean']) == len(raw)
    assert labeled['order_status'].eq('delivered').all()
    assert not ns['exclusion_mask'].loc[labeled.index].any()
    expected_labels = (labeled['order_delivered_customer_date'].dt.normalize() >
                       labeled['order_estimated_delivery_date'].dt.normalize()).astype(int)
    assert np.array_equal(labeled[ns['target_col']].to_numpy(), expected_labels.to_numpy())
    assert ns['y'].equals(ns['df_clean'].loc[ns['feature_eligible_mask'], ns['target_col']].astype(int))
    expected_medians = ns['X_unfilled'].median().fillna(0)
    expected_medians['max_product_photos'] = 0
    pd.testing.assert_series_equal(ns['feature_medians'], expected_medians)
    pd.testing.assert_frame_equal(features, ns['X_unfilled'].fillna(expected_medians))
    forbidden = ['payment', 'status', 'review', 'shipping_limit', 'delivered_', 'order_id', 'customer_id']
    assert not [c for c in features.columns if any(term in c for term in forbidden)]
    assert ns['order_ids'].is_unique
    assert ns['order_ids'].equals(ns['df_clean'].loc[ns['feature_eligible_mask'], 'order_id'])
    assert len(features) == int(ns['feature_eligible_mask'].sum())
    assert not (ns['no_items_mask'] | ns['unresolved_amount_mask']).loc[features.index].any()
    assert np.allclose(features['basket_price'], ns['df_pipeline']['basket_price_repaired'])
    assert np.allclose(features['total_freight'], ns['df_pipeline']['total_freight_repaired'])
    assert np.isclose(ns['audit_df']['Dropped Rows'].sum(), len(raw) - len(labeled))
    return {'assembled_orders': len(raw), 'labeled_orders': len(labeled), 'feature_orders': len(features), 'features': features.shape[1],
            'record_preservation': True, 'aligned_features_labels_ids': True,
            'final_predictor_columns_pass': True, 'finite_features': True,
            'calendar_labels_and_reliable_outcomes': True, 'full_dataset_imputation': True}



class NotebookObserver:
    def __init__(self, root, temporary, database):
        self.root, self.temporary, self.database = Path(root), Path(temporary), Path(database)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'sql').mkdir(exist_ok=True)
        self.sql = (self.root / 'sql' / 'notebook.sql').open('w')
        self.original_connect = sqlite3.connect
        self.connections = []
        def connect(*args, **kwargs):
            connection = self.original_connect(*args, **kwargs)
            connection.set_trace_callback(lambda query: self.sql.write(query.rstrip(';') + ';\n'))
            self.connections.append(connection)
            return connection
        sqlite3.connect = connect
        self.metrics, self.artifacts, self.charts = [], [], []
        self.baseline_rss = ResourceMeter(self.temporary).start_rss

    def start(self, stage):
        self.stage = stage
        self.plot_export_seconds = 0.0
        self.figure_count = 0
        self.meter = ResourceMeter(self.temporary, self.database).start()

    def install_plot_capture(self):
        import matplotlib.pyplot as plt
        self.original_show = plt.show
        def show(*args, **kwargs):
            started = time.perf_counter()
            for number in plt.get_fignums():
                self.figure_count += 1
                path = self.root / 'stages' / self.stage / f'chart_{self.figure_count:02d}.png'
                path.parent.mkdir(parents=True, exist_ok=True)
                plt.figure(number).savefig(path, dpi=100)
                self.charts.append({'stage': self.stage, 'path': str(path.relative_to(self.root)),
                                    'data': [f'stages/{self.stage}/{name}.csv' for name in CHART_DATA[self.stage][self.figure_count - 1]]})
            self.plot_export_seconds += time.perf_counter() - started
            return self.original_show(*args, **kwargs)
        plt.show = show

    def end(self, stage, ns):
        import pandas as pd
        calculation_end = time.perf_counter()
        export_started = calculation_end
        stage_artifacts = []
        for name, frame, meaning, scale in stage_bindings(stage, ns, self.database):
            stage_artifacts.append(write_frame(self.root, stage, name, frame, meaning, scale))
        self.artifacts.extend(stage_artifacts)
        if stage == '01_setup':
            self.install_plot_capture()
        if stage == '05_assembly':
            (self.root / 'sql' / 'assembly.sql').write_text(ns['assembly_query'].strip() + '\n')
        if stage == '16_final_features':
            dump_json(self.root / 'checks.json', validate_results(ns))
        export_seconds = time.perf_counter() - export_started + self.plot_export_seconds
        # Capture every retained intermediate's logical size without serializing duplicate data.
        inventory_started = time.perf_counter()
        frames = []
        for name, frame in list(ns.items()):
            if isinstance(frame, (pd.DataFrame, pd.Series)):
                memory = frame.memory_usage(index=True, deep=True)
                frames.append({'name': name, 'rows': len(frame),
                               'columns': len(frame.columns) if isinstance(frame, pd.DataFrame) else 1,
                               'logical_memory_bytes': int(memory.sum() if hasattr(memory, 'sum') else memory)})
        inventory_seconds = time.perf_counter() - inventory_started
        measurement = self.meter.stop()
        measurement.update({'stage': stage,
                            'calculation_seconds': max(0.0, calculation_end - self.meter.started - self.plot_export_seconds),
                            'export_seconds': export_seconds,
                            'inventory_seconds': inventory_seconds,
                            'saved_bytes': directory_bytes(self.root / 'stages' / stage),
                            'retained_logical_bytes': sum(f['logical_memory_bytes'] for f in frames),
                            'output_logical_bytes': sum(a['logical_memory_bytes'] for a in stage_artifacts),
                            'intermediates': frames})
        self.metrics.append(measurement)
        self.sql.flush()
        dump_json(self.root / 'metrics.json', self.metrics)
        dump_json(self.root / 'artifacts.json', self.artifacts)
        dump_json(self.root / 'charts.json', self.charts)

    def finish(self):
        for connection in self.connections:
            connection.close()
        sqlite3.connect = self.original_connect
        self.sql.close()
        dump_json(self.root / 'observer.json', {'baseline_rss_bytes': self.baseline_rss,
                                               'pid': os.getpid(), 'scope': 'IPython kernel process'})
