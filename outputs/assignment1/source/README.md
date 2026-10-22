# ENG2040 Assignment 1

Alnoor Ismail — Marketplace orders and delivery outcomes.

`ENG2040_final.ipynb` contains the analysis, cleaning rules and feature preparation. `run_pipeline.py` executes its unchanged code in an isolated Python kernel, saves each named step, and writes resource and seven-page assignment reports. The assignment requirements are in `assignment_01_brief.pdf`.

## One-time setup

Use Python 3.11 (validated with 3.11.15) and install the pinned dependencies in a virtual environment:

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The first installation requires access to a package index. Subsequent pipeline runs need no network. Keep `data/raw.sql`, `ENG2040_final.ipynb`, and the supporting Python files together in this project directory. No database server or separately registered Jupyter kernel is needed. The runner uses the interpreter that launches it.

## Reproduce all outputs

After setup, run this one command:

```sh
python run_pipeline.py
```

The runner rebuilds the database from `data/raw.sql`, calibrates estimates on a seeded sample, executes the full notebook, exports data and plots, validates the final datasets, and runs three equivalent-work benchmark trials per approach. It leaves the original notebook, SQL, and working `marketplace.sqlite` unchanged.

Outputs are written to `outputs/assignment1`. To choose a different destination, including a path with spaces:

```sh
python run_pipeline.py --output "outputs/another run"
```

The command can also be launched using an absolute script path from another working directory. Inputs and the default output path are resolved relative to the script.

A rerun replaces only a directory carrying this runner's ownership marker. A nonempty, unowned destination is rejected. Work happens in a sibling staging directory, and results are published only after successful checks. On a failure or interruption, the previous successful output remains available and the console identifies the diagnostic log. Do not edit generated files if you want those edits retained on a rerun. A forcibly killed process can leave a lock; inspect the PID recorded in that lock before removing it.

## Output map

All paths below are relative to the selected output directory. Every CSV has an adjacent `.schema.json` describing column types, null encoding, and row meaning. The manifest records exact filenames, checksums, dimensions, dependencies, chart-data links, and source hashes.

| Step / directory under `stages/` | Input | Saved outputs | Meaning of one row |
|---|---|---|---|
| `00_database` | Supplied `data/raw.sql` | `marketplace.sqlite` | Original source-table records, unchanged |
| `01_setup` | Pinned Python environment | Resource measurements; no dataset | Library setup has no tabular output |
| `02_inspection` | Rebuilt database | Table overview, schema, sample rows | A table, column, or sampled source record |
| `03_multiplicity` | Item/payment tables | Item and payment multiplicity | One source-level summary |
| `04_preservation` | Orders and order items | Basic merged orders, item aggregates, preservation checks | One order, or one audit summary |
| `05_assembly` | Source tables | `master_orders.csv` | One original order with aggregated child information |
| `06_original_benchmark` | Source tables | Both equivalent benchmark outputs and measurements | One order per approach; matching columns and values |
| `07_profile` | Assembled orders and source items | Numerical, text, timestamp, status and source audits | One check, column, status, or sampled item |
| `08_cleaning` | Assembly and profiling | `df_clean.csv`, `df_labeled.csv`, item cleaning tables, audits and sensitivity tables | Original cleaned order, usable labeled order, item, checkpoint, or policy/state summary |
| `09_eda_delivery` | Labeled orders | Delay-enriched orders, outcome counts, duration statistics, chart data | Order, outcome group, or statistic |
| `10_eda_window` | Delay-enriched orders | Window-enriched orders, outcome summary, window-band late rates, chart data | Order or delivery-outcome group |
| `11_eda_state` | Window-enriched orders | State summaries and displayed top states | Customer state |
| `12_eda_hypotheses` | Window-enriched orders | Photo, payment, and fulfillment summaries | Photo-count, payment-type, or fulfillment group |
| `13_eda_weight` | Window-enriched orders | Filtered scatter data | Late order with recorded weight below 50,000 g |
| `14_eda_sellers` | Labeled orders; helper defined in hypotheses | Seller and geographic summaries | Seller-count or seller-state-count group |
| `15_initial_features` | Window-enriched orders | Engineered orders, encodings, `X.csv`, `y.csv`, `order_ids.csv` | One feature-eligible order in the initial feature representation |
| `16_final_features` | Initial engineered orders | Engineered orders, numerical/categorical components, X before/after imputation, dataset fill values, full X/y/IDs | One feature-eligible order |
| `17_resources` | Notebook measurements and retained objects | `resource_df.csv`, `object_sizes.csv` | One measured step or retained object |

`07_profile` uses the existing assembly as its input rather than saving another identical copy of that DataFrame. Key/orphan checks, outlier profiles, and timestamp parse audits are also exported. All retained intermediate DataFrames still appear in the resource inventory. Masks in `order_audit.csv` are the notebook's actual masks, can overlap, and must not be summed as mutually exclusive reasons. The retention columns and cleaning audit provide the final row accounting.

**Use `16_final_features` for modeling**: both feature stages exclude payments, order status, reviews, shipment/delivery events, IDs and labels. The initial stage still contains missing numerical inputs. The final stage uses full-dataset median imputation and exports one aligned X/y/IDs dataset restricted to feature-eligible orders.

Cleaning preserves all source orders in `df_clean`; unreliable delivery outcomes remain unlabelled. Labels require delivered status, known purchase/delivery/estimate dates, consistent observed chronology, independently of item amounts. Delivery on the estimated calendar date is on time. Missing approval/carrier dates alone do not invalidate the outcome. The `order_audit` flags overlap; sequential cohort counts are in `audit_df`.

Item-level negative/missing prices and freight are flagged before aggregation. Nonpositive weight and negative photo counts become missing optional values rather than causing row loss. State codes are normalized before the local-seller flag is rebuilt; invalid geography becomes `unknown`. Large positive weights and valid zero prices remain. `selected_category` and `selected_payment_type` are alphabetically last source values, not dominant categories; they are not predictors.

**Units:** the raw assembly keeps payment values in source centavos. Cleaned payment totals are in BRL (divided by 100), like price and freight. Payment reconciliation should compare the payment total with basket price plus freight; payments never supply imputed predictors. Weights are grams; delays and promised windows are calendar days. Unknown local fulfillment remains missing until median imputation, with a missing indicator.

`df_labeled` contains every reliable delivery outcome, including orders with invalid amounts or no items. `feature_eligible_mask` additionally requires items and complete repaired price and freight totals. `audit_df.csv` describes delivery-label selection; `feature_audit_df.csv` starts from those reliable labels and separately removes orders without items or with unresolved amounts. `order_audit.csv` and `df_clean.csv` retain separate delivery and feature exclusion reasons. `item_repair_audit.csv` counts invalid, imputed, and unresolved item amounts.

Missing/negative item prices use the exact product's original valid median; freight uses the same seller/destination state's original valid median. Only original nonmissing, nonnegative values supply medians; zero is valid. Unknown matching keys and unmatched amounts remain missing, with no fallback. Original columns are preserved beside `price_repaired` and `freight_repaired`. Any unresolved item makes its corresponding repaired order total missing. Both feature stages use repaired totals under the existing predictor names `basket_price` and `total_freight`; the original order-level totals remain unchanged. Payments do not determine labels, repairs, or feature eligibility.

`sensitivity_df.csv` compares the date-only diagnostic, main reliable-delivery population, complete original amounts, repaired feature-eligible amounts, and existing approval/weight restrictions. `state_sensitivity.csv` repeats these comparisons by state. Existing bootstrap intervals and statistical tests are retained; groups with fewer than five events or non-events have intervals suppressed and cannot support interval-based national comparisons. The financial histogram uses available repaired basket prices and labels its denominator; log plots display positive values only.

Other deliverables:

- `executed.ipynb`: complete executed copy, including tagged observer cells; the source notebook is unchanged.
- `source/`: notebook and supporting-code snapshots. The original raw input remains in the project's `data/raw.sql` and is identified by its checksum.
- `sql/notebook.sql`: SQL executed by notebook and export observers. `sql/assembly.sql` is the exact full assembly query. Database initialization uses the supplied SQL; the source-import pilot SQL is saved in `calibration/`.
- `stages/*/chart_*.png`: all eleven figures. `charts.json` and the manifest link every figure to its exact CSV input. Original plot settings, including axis limits and filters, remain in the executed notebook.
- `reports/assignment_report.pdf` and `.md`: seven-page discussion of decisions, findings, features and limitations, regenerated by `assignment_report.py`.
- `reports/report.md`: estimated-versus-measured resource comparison and equivalent-work benchmark interpretation.
- `reports/resources.csv` and `.json`: per-stage measurements, predictions, signed/absolute differences, and percentage differences.
- `reports/measurements.json`: retained intermediate sizes, sampling scope, timing, and observed sample intervals.
- `reports/environment.json`: Python, package, SQLite, operating-system and hardware details.
- `calibration/`: sample selection, sampled SQL import, pilot database, executed pilot, pilot outputs and measurements.
- `benchmark/`: three fresh-process trials per equivalent assembly approach, logs, and summary.
- `checks.json` and `manifest.json`: correctness checks and the complete artifact inventory.

## Load the results

Read the rebuilt database using Python's `sqlite3` module or a SQLite client. To restore a CSV's saved types and missing values, use the supplied helper:

```python
from pipeline_support import read_frame

orders = read_frame("outputs/assignment1/stages/08_cleaning/df_labeled.csv")
X = read_frame("outputs/assignment1/stages/16_final_features/X.csv")
y = read_frame("outputs/assignment1/stages/16_final_features/y.csv")
ids = read_frame("outputs/assignment1/stages/16_final_features/order_ids.csv")

```

Rows in each X/y/IDs trio are aligned by position. Files retain notebook row order; indexes are not exported as predictors. IDs stay in their own files. CSVs use UTF-8 and the literal `\N` for missing values. Default CSV NA inference can corrupt textual values or identifiers: use the schema-aware helper. Lists in audit tables are JSON-encoded in CSV and restored by the helper.

The notebook prepares one complete numerical feature table, with separate labels and order IDs. Unknown maximum photo counts use zero as a numerical placeholder, with missing-photo flags retained. Other missing features use the prepared dataset's medians; entirely missing columns use zero plus a missing flag. `imputation_values.csv` records the fill values, and `X_unfilled.csv` preserves the inputs before imputation. State encoding uses the fixed 27-state vocabulary plus `unknown`.

For future model evaluation, refit both item-matching medians and predictor-fill medians using training data only. Rebuild repaired totals from original items after the split: `X_unfilled` already contains full-dataset item repairs and is not sufficient by itself to remove that leakage. Current full-dataset medians prepare this assignment's descriptive feature table.

The final mean weight is the actual mean of item weights and remains missing when any item weight is missing. Freight/price is missing for zero-price baskets. Numerical missing indicators preserve these distinctions after imputation. Raw and log prices are kept as baseline representations; no predictive importance is claimed. No model is trained or evaluated in this assignment.

## Resource measurement scope

Estimates are written before the full workload: database import uses a seeded SQL-statement pilot, and notebook stages use up to 2,000 seeded orders with related records. Calculations and exported order data scale by order count; grouped tables, image dimensions, schemas and library setup use fixed projections. The report lists assumptions and actual differences, rather than treating estimates as capacity guarantees.

Process RSS and visible temporary storage are sampled every 10 ms. The recorded maximum sample gap shows scheduling delays; short spikes may be missed. RSS includes previously retained intermediates and native allocations, while DataFrame `memory_usage(deep=True)` is a logical-size estimate that can count shared buffers twice. Those numbers are reported separately. Temporary storage covers the monitored scratch directories and SQLite journal/WAL/SHM files. Hidden/unlinked temporary SQLite files cannot be fully observed; zero means none observed.

The sampler covers calculation, export and intermediate inventory work. Calculation, export and inventory durations are separated; total stage elapsed time and concurrent sampling overhead are also recorded. Kernel startup/protocol overhead is in `execution.json`, calibration overhead in `reports/calibration.json`, and total run/benchmark durations in the manifest. All detailed storage values use bytes, and display tables use MiB.

The notebook and companion benchmarks compare the same 25 raw assembly columns and check values before accepting timings. Notebook tracemalloc measures traced Python allocations, while the companion benchmark samples process RSS. Three fresh processes per approach alternate execution order; package import and equivalence checks are outside timing, and filesystem caches are not flushed. GROUP_CONCAT list order is normalized only for equality; numeric sums use tight floating-point tolerances.

Data artifacts marked `deterministic: true` should have identical checksums on repeated runs in the documented environment. Runtime, memory, metadata timestamps and benchmark measurements vary. The resource report documents measurement scope; the separate seven-page assignment report covers business findings and methodology.

## Original database-only setup

`python setup_db.py` still imports the supplied SQL into the project working database without cleaning records. It refuses to overwrite an existing database. This command needs only Python's standard library; it is separate from the full notebook pipeline above.

