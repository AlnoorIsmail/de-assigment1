# Reproducibility and resource report

Regenerate this report and every named pipeline output with `python run_pipeline.py` after the documented environment setup.

## Estimated versus measured resources

Each cell below shows **estimate → measurement**. Memory/storage use MiB (1,048,576 bytes); durations use seconds. Full values and differences are in `resources.csv`.

| Step | Calculation s | Export s | Peak RSS MiB | Temporary MiB | Saved MiB | Retained logical MiB |
|---|---:|---:|---:|---:|---:|---:|
| Database creation | 0.366 → 0.294 | 0.000 → 0.000 | 258.735 → 202.641 | 0.009 → 0.001 | 23.200 → 23.234 | 0.000 → 0.000 |
| Library setup | 23.407 → 37.771 | 0.000 → 0.000 | 205.031 → 209.281 | 0.161 → 0.161 | 0.000 → 0.000 | 0.000 → 0.000 |
| Database inspection | 0.283 → 0.042 | 0.222 → 0.022 | 228.938 → 214.000 | 0.161 → 0.161 | 0.012 → 0.013 | 0.006 → 0.001 |
| Item and payment multiplicity | 0.088 → 0.020 | 0.027 → 0.002 | 233.000 → 217.422 | 0.161 → 0.161 | 0.001 → 0.001 | 0.009 → 0.001 |
| Record and value preservation | 0.241 → 0.111 | 0.048 → 0.005 | 267.062 → 230.219 | 0.161 → 0.161 | 0.003 → 0.003 | 0.097 → 0.079 |
| Order-level assembly | 0.405 → 0.289 | 0.215 → 0.164 | 368.781 → 297.844 | 0.161 → 0.161 | 5.211 → 5.221 | 20.907 → 20.901 |
| Equivalent notebook benchmark | 15.318 → 15.756 | 0.398 → 0.331 | 546.750 → 439.562 | 0.161 → 0.161 | 10.461 → 10.479 | 62.529 → 62.545 |
| Quality profiling and source verification | 0.722 → 0.289 | 0.118 → 15.026 | 553.469 → 444.094 | 0.161 → 0.161 | 0.007 → 0.007 | 89.063 → 89.030 |
| Cleaning, labeling, and exclusion audit | 6.394 → 5.234 | 1.016 → 0.750 | 675.656 → 495.578 | 0.161 → 0.161 | 20.508 → 20.504 | 142.239 → 141.492 |
| Delivery frequency and duration | 4.618 → 0.497 | 2.077 → 0.382 | 710.500 → 510.062 | 0.161 → 0.161 | 5.932 → 5.928 | 143.252 → 142.620 |
| Promised window and distributions | 17.119 → 1.899 | 4.723 → 0.717 | 898.781 → 530.078 | 0.161 → 0.161 | 6.863 → 6.852 | 144.963 → 144.314 |
| Customer-state performance | 2.991 → 0.393 | 0.972 → 0.132 | 971.281 → 530.156 | 0.161 → 0.161 | 0.048 → 0.069 | 145.065 → 144.330 |
| Photos, payments, and local fulfillment | 6.894 → 0.726 | 2.724 → 0.285 | 1066.281 → 530.188 | 0.161 → 0.161 | 0.116 → 0.114 | 146.201 → 145.401 |
| Weight and delay duration | 2.713 → 0.322 | 2.060 → 0.213 | 1082.375 → 530.438 | 0.161 → 0.161 | 0.063 → 0.108 | 147.968 → 147.481 |
| Seller complexity and comparison summary | 1.872 → 0.204 | 0.752 → 0.082 | 1112.219 → 530.453 | 0.161 → 0.161 | 0.035 → 0.037 | 148.284 → 147.759 |
| Approval-time features and state encoding | 0.129 → 0.034 | 0.417 → 0.319 | 1154.562 → 554.094 | 0.161 → 0.161 | 6.258 → 6.354 | 167.717 → 167.494 |
| Final features, labels and IDs | 0.318 → 0.041 | 1.392 → 1.030 | 1331.594 → 597.109 | 0.161 → 0.161 | 15.419 → 15.646 | 204.979 → 205.236 |
| Notebook resource summary | 0.165 → 0.064 | 0.038 → 0.004 | 1331.594 → 597.109 | 0.161 → 0.161 | 0.002 → 0.002 | 204.996 → 205.238 |

## Findings on this run

The largest sampled process footprint occurred during Final features, labels and IDs: 597.11 MiB measured versus 1331.59 MiB estimated. This includes data retained from earlier stages, not only that stage’s new allocations.

The longest calculation stage was Library setup (37.771 s). Final-feature saved storage was 15.65 MiB versus 15.42 MiB estimated (+1.5%).

Pilot scaling is most useful for row-dependent tables. Fixed display/plot costs and late package imports can make scaled runtime and RSS estimates conservative; sample category coverage can change encoded widths. Inspect the recorded differences rather than assuming linear scaling is exact.

## Methods and interpretation

- Estimates were saved before the corresponding full workload. The source-import pilot uses up to 2,000 INSERT statements per table; the notebook pilot uses up to 2,000 seeded orders with all related records.
- Runtime is a linear pilot projection. Initial library setup and its temporary caches are fixed. Peak RSS projects memory above the pilot library-setup baseline. Order-level CSVs and logical data sizes scale by order count; summary tables, schemas, and image sizes use fixed projections. Differences are expected for small samples, category coverage, plotting, sorting, allocation, late imports, and filesystem caches.
- RSS is sampled in the executing kernel (or database worker) every 10 ms, including exports and inventory collection. It includes native allocations and previously retained intermediates. Brief peaks can be missed; actual maximum sample gaps are recorded.
- Temporary storage is the sampled visible scratch-directory size plus SQLite journal/WAL/SHM sizes. It excludes the persistent working database. Unlinked or hidden SQLite temporary files and internal memory allocations are not fully observable; zero means none observed, not proof of no temporary resource use.
- Logical DataFrame memory uses `memory_usage(deep=True)`, including indexes. Shared buffers may be counted more than once; this is not physical RAM. Every retained intermediate is listed in `measurements.json`.
- Calculation time excludes the observer’s CSV/PNG export time. Export and inventory durations are reported separately. Inline notebook rendering remains part of calculation. Sampling runs concurrently, so its overhead is not subtracted from wall time.
- Saved bytes per stage cover stage tables, schemas, and PNGs; database creation covers the database file. The manifest separately inventories notebooks, SQL, source snapshots, calibration files, and reports.
- Percentage differences are undefined when the estimate is zero and are left blank in CSV.

## Equivalent-work assembly benchmark

| Approach | Median calculation s | Maximum sampled RSS MiB | Rows | Columns |
|---|---:|---:|---:|---:|
| sql | 0.1490 | 118.73 | 20000 | 25 |
| pandas | 3.8523 | 146.83 | 20000 | 25 |

Both alternatives produce the complete order-level assembly and pass value-equivalence checks before results are accepted. The benchmark preserves SQL MAX selections, nullable sums, distinct counts and the local-seller flag. GROUP_CONCAT ordering is unspecified and is normalized only during comparison.

These are three fresh-process trials per approach, with alternating execution order. Imports and correctness checks are outside the measured operation. OS caches are not flushed. The explicit Pandas implementation prioritizes matching SQLite semantics; the comparison is evidence for these implementations, not a claim about all SQL or Pandas programs.

The notebook benchmark also checks equivalent outputs. Its tracemalloc results cover traced Python allocations, not total process RAM. Use the fresh-process RSS comparison above for physical process memory.

## Execution scope

- Calibration wall time: 47.885 s.
- Timing, memory, environment metadata and executed-notebook timestamps are machine/run dependent. Data-artifact checksums identify repeatable outputs.
- The notebook applies source-item checks, calendar-date labels, chronology checks and full-dataset median imputation. It exports one feature table with separate labels and IDs. Checks validate reliable outcomes, finite features, imputation values and row alignment. Inclusion sensitivity is exported with the cleaning stage.
