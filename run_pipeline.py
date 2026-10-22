#!/usr/bin/env python3
"""Reproduce ENG2040_final.ipynb, its stage data, and measured resource reports."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import random
import re
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parent
REQUIRED = {'pandas': 'pandas', 'numpy': 'numpy', 'matplotlib': 'matplotlib', 'seaborn': 'seaborn',
            'sklearn': 'scikit-learn', 'scipy': 'scipy', 'nbformat': 'nbformat', 'nbclient': 'nbclient',
            'ipykernel': 'ipykernel', 'psutil': 'psutil'}


def check_dependencies():
    missing = [package for module, package in REQUIRED.items() if importlib.util.find_spec(module) is None]
    if missing:
        raise RuntimeError('Missing dependencies: ' + ', '.join(missing) +
                           f'. Run: {sys.executable} -m pip install -r "{ROOT / "requirements.txt"}"')


def validate_notebook(notebook):
    from pipeline_support import STAGES
    expected = [cell_id for _, _, ids, _ in STAGES for cell_id in ids]
    actual = [c['id'] for c in notebook['cells'] if c['cell_type'] == 'code']
    if actual != expected:
        raise ValueError('Notebook stage identifiers or execution order changed. Update the explicit stage map before running; no stages were skipped.')


def environment(temporary):
    temporary = Path(temporary)
    temporary.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({'TMPDIR': str(temporary), 'TEMP': str(temporary), 'TMP': str(temporary),
                'SQLITE_TMPDIR': str(temporary), 'MPLCONFIGDIR': str(temporary / 'matplotlib'),
                'IPYTHONDIR': str(temporary / 'ipython'), 'JUPYTER_RUNTIME_DIR': str(temporary / 'jupyter'),
                'MPLBACKEND': 'module://matplotlib_inline.backend_inline', 'PYTHONHASHSEED': '0',
                'PYTHONDONTWRITEBYTECODE': '1',
                'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ.get('PATH', '')})
    return env


def execute_notebook(notebook, root, database, temporary, label):
    import nbformat
    from nbclient import NotebookClient
    from jupyter_client import AsyncKernelManager
    from jupyter_client.kernelspec import KernelSpec
    from pipeline_support import STAGES, dump_json
    started = time.perf_counter()
    notebook = copy.deepcopy(notebook)
    stages_by_start = {ids[0]: stage for stage, _, ids, _ in STAGES}
    stages_by_end = {ids[-1]: stage for stage, _, ids, _ in STAGES}
    def observer(source, **metadata):
        cell = nbformat.v4.new_code_cell(source)
        cell.metadata = {'tags': ['pipeline-observer'], **metadata}
        return cell
    cells = [observer(
        f'import sys\nsys.path.insert(0, {str(ROOT)!r})\n'
        'from pipeline_support import NotebookObserver\n'
        f'_pipeline_observer = NotebookObserver({str(root)!r}, {str(temporary)!r}, {str(database)!r})')]
    for cell in notebook.cells:
        if cell.cell_type == 'code':
            if cell.id in stages_by_start:
                stage = stages_by_start[cell.id]
                cells.append(observer(f'_pipeline_observer.start({stage!r})', pipeline_start=stage))
            cell.outputs = []
            cell.execution_count = None
        cells.append(cell)
        if cell.cell_type == 'code' and cell.id in stages_by_end:
            stage = stages_by_end[cell.id]
            cells.append(observer(f'_pipeline_observer.end({stage!r}, globals())', pipeline_end=stage))
    cells.append(observer('_pipeline_observer.finish()'))
    notebook.cells = cells
    notebook.metadata.kernelspec = {'name': 'python3', 'display_name': 'Pipeline Python', 'language': 'python'}
    root, temporary = Path(root), Path(temporary)
    root.mkdir(parents=True, exist_ok=True)
    env = environment(temporary)
    manager = AsyncKernelManager(connection_file=str(temporary / 'kernel.json'))
    manager._kernel_spec = KernelSpec(argv=[sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}'],
                                      display_name='Pipeline Python', language='python')
    def progress(cell, **kwargs):
        if cell.metadata.get('pipeline_end') and not any(o.output_type == 'error' for o in cell.get('outputs', [])):
            print(f'{label}: {cell.metadata.pipeline_end} complete', flush=True)
    client = NotebookClient(notebook, km=manager, timeout=600, allow_errors=False,
                            on_cell_executed=progress, ipython_hist_file=':memory:')
    try:
        client.execute(cwd=str(Path(database).parent), env=env, cleanup_kc=True)
    finally:
        nbformat.write(notebook, root / 'executed.ipynb')
    total = time.perf_counter() - started
    metrics = json.loads((root / 'metrics.json').read_text())
    dump_json(root / 'execution.json', {'wall_seconds': total,
                                       'kernel_startup_and_protocol_seconds': max(0, total - sum(m['elapsed_seconds'] for m in metrics)),
                                       'interpreter': sys.executable})
    return metrics


def source_sample(source, destination):
    """Reservoir-sample up to 2,000 INSERT statements per table, keeping DDL and order."""
    rng = random.Random(42)
    reservoirs, counts, other = {}, {}, []
    statement, index = '', 0
    with Path(source).open() as stream:
        for line in stream:
            statement += line
            if not sqlite3.complete_statement(statement):
                continue
            match = re.match(r'\s*INSERT INTO\s+"?([a-z_]+)"?', statement, re.IGNORECASE)
            if match:
                table = match.group(1)
                counts[table] = counts.get(table, 0) + 1
                sample = reservoirs.setdefault(table, [])
                if len(sample) < 2000:
                    sample.append((index, statement))
                else:
                    slot = rng.randrange(counts[table])
                    if slot < 2000:
                        sample[slot] = (index, statement)
            else:
                other.append((index, statement))
            index += 1
            statement = ''
    if statement.strip():
        raise ValueError('The source SQL ends with an incomplete statement.')
    if not counts:
        raise ValueError('No source INSERT statements found for calibration.')
    statements = other + [item for sample in reservoirs.values() for item in sample]
    Path(destination).write_text(''.join(sql for _, sql in sorted(statements)))
    return {'seed': 42, 'maximum_statements_per_table': 2000,
            'source_inserts_by_table': counts,
            'sample_inserts_by_table': {name: len(values) for name, values in reservoirs.items()}}


def database_worker(sql, database, temporary, result):
    from pipeline_support import ResourceMeter, dump_json
    from setup_db import populate
    meter = ResourceMeter(temporary, database).start()
    tables, rows = populate(Path(sql), Path(database))
    metrics = meter.stop()
    metrics.update({'stage': '00_database', 'calculation_seconds': metrics['elapsed_seconds'], 'export_seconds': 0.0,
                    'inventory_seconds': 0.0, 'saved_bytes': Path(database).stat().st_size,
                    'input_bytes': Path(sql).stat().st_size, 'source_rows': rows, 'tables': tables,
                    'intermediates': [{'name': 'SQL source text', 'logical_memory_bytes': Path(sql).stat().st_size}],
                    'retained_logical_bytes': 0, 'output_logical_bytes': 0})
    dump_json(result, metrics)


def run_worker(arguments, temporary, log):
    started = time.perf_counter()
    with Path(log).open('w') as stream:
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), *arguments],
                                   cwd=str(ROOT), env=environment(temporary), stdout=stream, stderr=subprocess.STDOUT)
        try:
            code = process.wait()
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
    if code:
        raise RuntimeError(f'Worker failed (exit {code}); see {log}:\n{Path(log).read_text()[-5000:]}')
    return time.perf_counter() - started


def relational_pilot(source, destination):
    """Keep sampled orders and all matching children/catalogue references."""
    rng = random.Random(42)
    with sqlite3.connect(f'file:{source}?mode=ro', uri=True) as connection:
        ids = [r[0] for r in connection.execute('SELECT order_id FROM orders ORDER BY order_id')]
        selected = sorted(rng.sample(ids, min(2000, len(ids))))
        connection.execute('ATTACH DATABASE ? AS pilot', (str(destination),))
        connection.execute('CREATE TEMP TABLE selected_orders (order_id TEXT PRIMARY KEY)')
        connection.executemany('INSERT INTO selected_orders VALUES (?)', [(value,) for value in selected])
        for name, sql in connection.execute("SELECT name, sql FROM main.sqlite_master WHERE type='table' ORDER BY name").fetchall():
            with sqlite3.connect(destination) as target:
                target.execute(sql)
        predicates = {
            'orders': 'order_id IN (SELECT order_id FROM selected_orders)',
            'order_items': 'order_id IN (SELECT order_id FROM selected_orders)',
            'order_payments': 'order_id IN (SELECT order_id FROM selected_orders)',
            'order_reviews': 'order_id IN (SELECT order_id FROM selected_orders)',
            'customers': 'customer_id IN (SELECT customer_id FROM orders WHERE order_id IN (SELECT order_id FROM selected_orders))',
            'products': 'product_id IN (SELECT product_id FROM order_items WHERE order_id IN (SELECT order_id FROM selected_orders))',
            'sellers': 'seller_id IN (SELECT seller_id FROM order_items WHERE order_id IN (SELECT order_id FROM selected_orders))',
            'category_translation': '1=1',
        }
        for table, predicate in predicates.items():
            connection.execute(f'INSERT INTO pilot.{table} SELECT * FROM main.{table} WHERE {predicate}')
        connection.commit()
    return {'seed': 42, 'sample_orders': len(selected), 'full_orders': len(ids), 'order_ids': selected}


def estimates(pilot_root, ratio, database_estimate):
    from pipeline_support import directory_bytes
    pilot_root = Path(pilot_root)
    metrics = json.loads((pilot_root / 'metrics.json').read_text())
    artifacts = json.loads((pilot_root / 'artifacts.json').read_text())
    # Library/font-cache setup is fixed overhead, not ten times larger for ten times the rows.
    setup = next(metric for metric in metrics if metric['stage'] == '01_setup')
    baseline = setup['peak_rss_bytes']
    fixed_temporary = setup['peak_temporary_bytes']
    result = [database_estimate]
    for metric in metrics:
        stage = metric['stage']
        factor = 1.0 if stage == '01_setup' else ratio
        data = [a for a in artifacts if a['stage'] == stage]
        output_bytes = sum(a['bytes'] * (ratio if a['projection_scale'] == 'orders' else 1) + a['schema_bytes'] for a in data)
        non_data = metric['saved_bytes'] - sum(a['bytes'] + a['schema_bytes'] for a in data)
        output_bytes += max(0, non_data)  # Plot dimensions and schema overhead are fixed.
        result.append({'stage': stage, 'calculation_seconds': metric['calculation_seconds'] * factor,
                       'export_seconds': metric['export_seconds'] * (factor if data else 1),
                       'peak_rss_bytes': baseline + max(0, metric['peak_rss_bytes'] - baseline) * factor,
                       'peak_temporary_bytes': fixed_temporary + max(0, metric['peak_temporary_bytes'] - fixed_temporary) * factor,
                       'saved_bytes': output_bytes,
                       'retained_logical_bytes': metric['retained_logical_bytes'] * factor,
                       'output_logical_bytes': sum(a['logical_memory_bytes'] * (ratio if a['projection_scale'] == 'orders' else 1) for a in data),
                       'scale_factor': factor,
                       'method': 'Pilot incremental RSS above library-setup baseline and compute/export time scaled by order count; initial libraries/temp caches, grouped output rows, schemas and plots use fixed-size projections.'})
    return result


def benchmark_worker(approach, database, query, temporary, result):
    import pandas as pd
    from pipeline_support import ResourceMeter, dump_json
    from pipeline_benchmark import pandas_assembly, sql_assembly, assert_equivalent
    meter = ResourceMeter(temporary, database).start()
    frame = pandas_assembly(database) if approach == 'pandas' else sql_assembly(database, query)
    metrics = meter.stop()
    # Validation is outside the timed/sampled comparison region.
    reference = sql_assembly(database, query)
    assert_equivalent(frame, reference)
    metrics.update({'approach': approach, 'rows': len(frame), 'columns': len(frame.columns),
                    'logical_output_bytes': int(frame.memory_usage(deep=True, index=True).sum()),
                    'equivalent': True})
    dump_json(result, metrics)


def benchmark(root, database, temporary):
    from pipeline_support import dump_json
    folder = Path(root) / 'benchmark'
    folder.mkdir()
    results = []
    for trial in range(1, 4):
        # Alternate the order to reduce systematic filesystem-cache ordering effects.
        for approach in (['sql', 'pandas'] if trial % 2 else ['pandas', 'sql']):
            print(f'Equivalent benchmark: {approach}, trial {trial}/3', flush=True)
            result = folder / f'{approach}_{trial}.json'
            worker_wall = run_worker(['--internal-benchmark', approach, str(database), str(Path(root) / 'sql' / 'assembly.sql'),
                                      str(temporary), str(result)], temporary, folder / f'{approach}_{trial}.log')
            metrics = json.loads(result.read_text())
            metrics['trial'] = trial
            metrics['worker_wall_seconds'] = worker_wall
            results.append(metrics)
    summary = []
    for approach in ['sql', 'pandas']:
        rows = [r for r in results if r['approach'] == approach]
        summary.append({'approach': approach,
                        'median_seconds': statistics.median(r['elapsed_seconds'] for r in rows),
                        'max_peak_rss_bytes': max(r['peak_rss_bytes'] for r in rows),
                        'max_temporary_bytes': max(r['peak_temporary_bytes'] for r in rows),
                        'rows': rows[0]['rows'], 'columns': rows[0]['columns'], 'equivalent': True})
    dump_json(folder / 'results.json', {'trials': results, 'summary': summary,
              'scope': 'Fresh Python process per trial; imports and equality validation excluded from timing. Filesystem cache is not flushed. RSS is process memory. GROUP_CONCAT order is normalized for equality only; floating sums allow 1e-9 absolute / 1e-12 relative tolerance.'})
    return summary


def write_reports(root, estimated, measured, calibration, benchmark_results, environment_details):
    import pandas as pd
    from pipeline_support import dump_json, STAGES
    root = Path(root)
    folder = root / 'reports'
    folder.mkdir(exist_ok=True)
    names = {'00_database': 'Database creation', **{s: name for s, name, _, _ in STAGES}}
    estimate_map = {e['stage']: e for e in estimated}
    rows = []
    fields = ['calculation_seconds', 'export_seconds', 'peak_rss_bytes', 'peak_temporary_bytes',
              'saved_bytes', 'retained_logical_bytes', 'output_logical_bytes']
    for actual in measured:
        estimate = estimate_map[actual['stage']]
        row = {'stage': actual['stage'], 'name': names[actual['stage']],
               'elapsed_seconds': actual['elapsed_seconds'], 'start_rss_bytes': actual['start_rss_bytes'],
               'peak_rss_increase_bytes': actual['peak_rss_increase_bytes'],
               'sampling_overhead_seconds': actual['sampling_overhead_seconds'],
               'inventory_seconds': actual['inventory_seconds'],
               'maximum_sample_gap_seconds': actual['maximum_sample_gap_seconds']}
        for field in fields:
            expected, value = estimate[field], actual[field]
            row[f'estimated_{field}'] = expected
            row[f'measured_{field}'] = value
            row[f'difference_{field}'] = value - expected
            row[f'absolute_difference_{field}'] = abs(value - expected)
            row[f'percent_difference_{field}'] = (value - expected) / expected * 100 if expected else None
        rows.append(row)
    pd.DataFrame(rows).to_csv(folder / 'resources.csv', index=False)
    dump_json(folder / 'resources.json', rows)
    dump_json(folder / 'measurements.json', measured)
    dump_json(folder / 'calibration.json', calibration)
    dump_json(folder / 'environment.json', environment_details)
    lines = ['# Reproducibility and resource report', '',
             'Regenerate this report and every named pipeline output with `python run_pipeline.py` after the documented environment setup.', '',
             '## Estimated versus measured resources', '',
             'Each cell below shows **estimate → measurement**. Memory/storage use MiB (1,048,576 bytes); durations use seconds. Full values and differences are in `resources.csv`.', '',
             '| Step | Calculation s | Export s | Peak RSS MiB | Temporary MiB | Saved MiB | Retained logical MiB |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        values = []
        for field in fields[:6]:
            divisor = 1 if field.endswith('seconds') else 1024 ** 2
            values.append(f'{row["estimated_" + field] / divisor:.3f} → {row["measured_" + field] / divisor:.3f}')
        lines.append('| ' + names[row['stage']] + ' | ' + ' | '.join(values) + ' |')
    largest = max(rows, key=lambda row: row['measured_peak_rss_bytes'])
    slowest = max(rows, key=lambda row: row['measured_calculation_seconds'])
    final_row = next(row for row in rows if row['stage'] == '16_final_features')
    lines += ['', '## Findings on this run', '',
              f'The largest sampled process footprint occurred during {largest["name"]}: '
              f'{largest["measured_peak_rss_bytes"] / 1024**2:.2f} MiB measured versus '
              f'{largest["estimated_peak_rss_bytes"] / 1024**2:.2f} MiB estimated. '
              'This includes data retained from earlier stages, not only that stage’s new allocations.', '',
              f'The longest calculation stage was {slowest["name"]} ({slowest["measured_calculation_seconds"]:.3f} s). '
              f'Final-feature saved storage was {final_row["measured_saved_bytes"] / 1024**2:.2f} MiB versus '
              f'{final_row["estimated_saved_bytes"] / 1024**2:.2f} MiB estimated '
              f'({final_row["percent_difference_saved_bytes"]:+.1f}%).', '',
              'Pilot scaling is most useful for row-dependent tables. Fixed display/plot costs and late package imports can make scaled runtime and RSS estimates conservative; sample category coverage can change encoded widths. Inspect the recorded differences rather than assuming linear scaling is exact.', '',
              '## Methods and interpretation', '',
              '- Estimates were saved before the corresponding full workload. The source-import pilot uses up to 2,000 INSERT statements per table; the notebook pilot uses up to 2,000 seeded orders with all related records.',
              '- Runtime is a linear pilot projection. Initial library setup and its temporary caches are fixed. Peak RSS projects memory above the pilot library-setup baseline. Order-level CSVs and logical data sizes scale by order count; summary tables, schemas, and image sizes use fixed projections. Differences are expected for small samples, category coverage, plotting, sorting, allocation, late imports, and filesystem caches.',
              '- RSS is sampled in the executing kernel (or database worker) every 10 ms, including exports and inventory collection. It includes native allocations and previously retained intermediates. Brief peaks can be missed; actual maximum sample gaps are recorded.',
              '- Temporary storage is the sampled visible scratch-directory size plus SQLite journal/WAL/SHM sizes. It excludes the persistent working database. Unlinked or hidden SQLite temporary files and internal memory allocations are not fully observable; zero means none observed, not proof of no temporary resource use.',
              '- Logical DataFrame memory uses `memory_usage(deep=True)`, including indexes. Shared buffers may be counted more than once; this is not physical RAM. Every retained intermediate is listed in `measurements.json`.',
              '- Calculation time excludes the observer’s CSV/PNG export time. Export and inventory durations are reported separately. Inline notebook rendering remains part of calculation. Sampling runs concurrently, so its overhead is not subtracted from wall time.',
              '- Saved bytes per stage cover stage tables, schemas, and PNGs; database creation covers the database file. The manifest separately inventories notebooks, SQL, source snapshots, calibration files, and reports.',
              '- Percentage differences are undefined when the estimate is zero and are left blank in CSV.', '',
              '## Equivalent-work assembly benchmark', '',
              '| Approach | Median calculation s | Maximum sampled RSS MiB | Rows | Columns |',
              '|---|---:|---:|---:|---:|']
    for result in benchmark_results:
        lines.append(f'| {result["approach"]} | {result["median_seconds"]:.4f} | {result["max_peak_rss_bytes"] / 1024**2:.2f} | {result["rows"]} | {result["columns"]} |')
    lines += ['', 'Both alternatives produce the complete order-level assembly and pass value-equivalence checks before results are accepted. The benchmark preserves SQL MAX selections, nullable sums, distinct counts and the local-seller flag. GROUP_CONCAT ordering is unspecified and is normalized only during comparison.', '',
              'These are three fresh-process trials per approach, with alternating execution order. Imports and correctness checks are outside the measured operation. OS caches are not flushed. The explicit Pandas implementation prioritizes matching SQLite semantics; the comparison is evidence for these implementations, not a claim about all SQL or Pandas programs.', '',
              'The notebook benchmark also checks equivalent outputs. Its tracemalloc results cover traced Python allocations, not total process RAM. Use the fresh-process RSS comparison above for physical process memory.', '',
              '## Execution scope', '',
              f'- Calibration wall time: {calibration["wall_seconds"]:.3f} s.',
              '- Timing, memory, environment metadata and executed-notebook timestamps are machine/run dependent. Data-artifact checksums identify repeatable outputs.',
              '- The notebook applies source-item checks, calendar-date labels, chronology checks and full-dataset median imputation. It exports one feature table with separate labels and IDs. Checks validate reliable outcomes, finite features, imputation values and row alignment. Inclusion sensitivity is exported with the cleaning stage.', '']
    (folder / 'report.md').write_text('\n'.join(lines))


def validate_destination(destination):
    from pipeline_support import OWNER
    destination = Path(destination)
    if destination.is_symlink():
        raise ValueError('Output must not be a symbolic link.')
    resolved = destination.resolve()
    if resolved == ROOT or resolved in ROOT.parents:
        raise ValueError('Output must not be the project directory or one of its parents.')
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        marker = destination / '.pipeline-owned.json'
        if not marker.is_file() or json.loads(marker.read_text()).get('owner') != OWNER:
            raise ValueError('Refusing to replace an unowned, nonempty output directory. Choose --output with an empty/new directory.')
    return resolved


def publish(staging, destination):
    """Replace only an owned output tree, with rollback if the final rename fails."""
    validate_destination(destination)
    previous = destination.with_name('.' + destination.name + '.previous-' + uuid.uuid4().hex[:8])
    if destination.exists():
        destination.rename(previous)
    try:
        staging.rename(destination)
    except BaseException:
        if previous.exists():
            previous.rename(destination)
        raise
    if previous.exists():
        shutil.rmtree(previous)


def run(output):
    from pipeline_support import STAGES, CHART_DATA, OWNER, directory_bytes, dump_json, sha256
    import nbformat
    import psutil
    started = time.perf_counter()
    source, notebook_path = ROOT / 'data' / 'raw.sql', ROOT / 'ENG2040_final.ipynb'
    for path in [source, notebook_path]:
        if not path.is_file():
            raise FileNotFoundError(f'Required input is missing: {path}')
    notebook_bytes = notebook_path.read_bytes()
    notebook = nbformat.reads(notebook_bytes.decode(), as_version=4)
    nbformat.validate(notebook)
    validate_notebook(notebook)
    destination = validate_destination(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock = destination.with_name('.' + destination.name + '.lock')
    try:
        with lock.open('x') as stream:
            stream.write(str(os.getpid()))
    except FileExistsError as error:
        raise RuntimeError(f'Another run may be active: {lock}. If it was forcibly killed, verify its PID before removing the lock.') from error
    staging = Path(tempfile.mkdtemp(prefix='.' + destination.name + '.run-', dir=destination.parent))
    temporary = staging / '.temporary'
    temporary.mkdir()
    try:
        dump_json(staging / '.pipeline-owned.json', {'owner': OWNER})
        source_root = staging / 'source'
        source_root.mkdir()
        (source_root / 'ENG2040_final.ipynb').write_bytes(notebook_bytes)
        for name in ['run_pipeline.py', 'pipeline_support.py', 'pipeline_benchmark.py', 'assignment_report.py', 'setup_db.py', 'requirements.txt', 'README.md']:
            shutil.copy2(ROOT / name, source_root / name)
        input_hash = sha256(source)
        calibration_started = time.perf_counter()
        calibration_root = staging / 'calibration'
        calibration_root.mkdir()
        sample_sql = calibration_root / 'source_sample.sql'
        sampling = source_sample(source, sample_sql)
        sample_result = calibration_root / 'source_import.json'
        print('Calibrating database import...', flush=True)
        run_worker(['--internal-load', str(sample_sql), str(calibration_root / 'source_sample.sqlite'), str(temporary), str(sample_result)], temporary, calibration_root / 'source_import.log')
        sample = json.loads(sample_result.read_text())
        factor = source.stat().st_size / sample_sql.stat().st_size
        db_estimate = {'stage': '00_database', 'scale_factor': factor,
                       'calculation_seconds': sample['calculation_seconds'] * factor, 'export_seconds': 0.0,
                       'peak_rss_bytes': sample['start_rss_bytes'] + sample['peak_rss_increase_bytes'] * factor,
                       'peak_temporary_bytes': sample['peak_temporary_bytes'] * factor,
                       'saved_bytes': sample['saved_bytes'] * factor,
                       'retained_logical_bytes': 0, 'output_logical_bytes': 0,
                       'method': 'Seeded INSERT-statement sample, scaled by SQL file bytes; fixed worker baseline kept separate.'}
        dump_json(calibration_root / 'database_estimate.json', db_estimate)
        database_folder = staging / 'stages' / '00_database'
        database_folder.mkdir(parents=True)
        database = database_folder / 'marketplace.sqlite'
        print('Rebuilding the full database from data/raw.sql...', flush=True)
        db_result = staging / 'database_metrics.json'
        db_wall = run_worker(['--internal-load', str(source), str(database), str(temporary), str(db_result)], temporary, staging / 'database.log')
        db_metrics = json.loads(db_result.read_text())
        db_metrics['worker_startup_and_protocol_seconds'] = max(0, db_wall - db_metrics['elapsed_seconds'])
        pilot_root = calibration_root / 'pilot'
        pilot_root.mkdir()
        pilot_database = pilot_root / 'marketplace.sqlite'
        selection = relational_pilot(database, pilot_database)
        dump_json(calibration_root / 'sample_selection.json', selection)
        # Pilot scratch is separate so its font/runtime caches do not bias full scratch metrics.
        pilot_metrics = execute_notebook(notebook, pilot_root, pilot_database, temporary / 'pilot', 'Pilot')
        ratio = selection['full_orders'] / selection['sample_orders']
        estimated = estimates(pilot_root, ratio, db_estimate)
        dump_json(staging / 'estimates.json', {'created_at_utc': datetime.now(timezone.utc).isoformat(),
                  'before_full_notebook_execution': True, 'stages': estimated})
        calibration_seconds = time.perf_counter() - calibration_started - db_wall
        # Discard pilot scratch before full measurements; the pilot data and measurements remain saved.
        shutil.rmtree(temporary)
        temporary.mkdir()
        measured = execute_notebook(notebook, staging, database, temporary, 'Full run')
        checks = json.loads((staging / 'checks.json').read_text())
        dump_json(staging / 'checks.json', checks)
        bench_started = time.perf_counter()
        bench = benchmark(staging, database, temporary / 'benchmark')
        bench_wall = time.perf_counter() - bench_started
        details = {'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(),
                   'machine': platform.machine(), 'logical_cpus': psutil.cpu_count(),
                   'physical_cpus': psutil.cpu_count(logical=False), 'host_memory_bytes': psutil.virtual_memory().total,
                   'sqlite': sqlite3.sqlite_version, 'packages': {name: importlib.metadata.version(name) for name in REQUIRED.values()},
                   'installed_distributions': {d.metadata['Name']: d.version for d in importlib.metadata.distributions() if d.metadata.get('Name')}}
        calibration = {**sampling, 'sample_orders': selection['sample_orders'], 'full_orders': selection['full_orders'],
                       'wall_seconds': calibration_seconds, 'saved_bytes': directory_bytes(calibration_root),
                       'source_sample_metrics': sample, 'notebook_metrics': pilot_metrics}
        write_reports(staging, estimated, [db_metrics, *measured], calibration, bench, details)
        os.environ.setdefault('MPLCONFIGDIR', str(temporary / 'report-matplotlib'))
        from assignment_report import write_assignment_report
        write_assignment_report(staging)
        shutil.rmtree(temporary)
        if notebook_path.read_bytes() != notebook_bytes or sha256(source) != input_hash:
            raise RuntimeError('Notebook or SQL input changed during the run; refusing to publish mixed-version outputs.')
        artifacts = json.loads((staging / 'artifacts.json').read_text())
        charts = json.loads((staging / 'charts.json').read_text())
        expected_charts = sum(len(groups) for groups in CHART_DATA.values())
        if len(charts) != expected_charts:
            raise AssertionError(f'Expected {expected_charts} figures, got {len(charts)}')
        for chart in charts:
            for path in [chart['path'], *chart['data']]:
                if not (staging / path).is_file():
                    raise AssertionError(f'Missing chart artifact: {path}')
        all_files = [{'path': str(path.relative_to(staging)), 'bytes': path.stat().st_size, 'sha256': sha256(path)}
                     for path in sorted(staging.rglob('*')) if path.is_file()]
        manifest = {'owner': OWNER, 'created_at_utc': datetime.now(timezone.utc).isoformat(),
                    'command': 'python run_pipeline.py', 'source_sql_sha256': input_hash,
                    'source_sql': 'data/raw.sql (supplied project input)',
                    'notebook_sha256': sha256(notebook_path), 'code_unchanged': True,
                    'stages': [{'id': '00_database', 'name': 'Database creation', 'inputs': ['data/raw.sql'],
                                'outputs': ['stages/00_database/marketplace.sqlite']}] +
                              [{'id': stage, 'name': name, 'cell_ids': ids, 'inputs': inputs,
                                'outputs': [a['path'] for a in artifacts if a['stage'] == stage],
                                'measurement': f'reports/resources.csv: {stage}'} for stage, name, ids, inputs in STAGES],
                    'artifacts': artifacts, 'charts': charts, 'files': all_files,
                    'saved_total_bytes_excluding_manifest': sum(f['bytes'] for f in all_files),
                    'wall_seconds_before_publication': time.perf_counter() - started,
                    'calibration_wall_seconds': calibration_seconds, 'benchmark_wall_seconds': bench_wall,
                    'checks': checks,
                    'reproducibility_scope': 'Data CSV hashes with deterministic=true. Timing, RSS, SQL import logs, environment details, and executed notebook metadata are not required to match across runs.'}
        dump_json(staging / 'manifest.json', manifest)
        publish(staging, destination)
        print(f'Complete: {destination}\nReport: {destination / "reports" / "report.md"}', flush=True)
        return destination
    except BaseException:
        if staging.exists():
            (staging / 'failure.log').write_text(traceback.format_exc())
            print(f'Run failed; previous successful output was preserved. Diagnostics: {staging / "failure.log"}', file=sys.stderr)
        raise
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs' / 'assignment1', help='Managed output directory (default: outputs/assignment1 beside this script).')
    parser.add_argument('--internal-load', nargs=4, help=argparse.SUPPRESS)
    parser.add_argument('--internal-benchmark', nargs=5, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        check_dependencies()
        if args.internal_load:
            database_worker(*args.internal_load)
        elif args.internal_benchmark:
            benchmark_worker(*args.internal_benchmark)
        else:
            run(args.output.expanduser())
        return 0
    except KeyboardInterrupt:
        print('Interrupted. No incomplete output was published.', file=sys.stderr)
        return 130
    except Exception as error:
        print(f'Pipeline error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
