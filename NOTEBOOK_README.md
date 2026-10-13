# Marketplace assignment notebook

Open `marketplace_assignment.ipynb` in Jupyter and run the cells in order. The delivered notebook
also contains results from a completed run. Its five main sections match the assignment brief.

Use Python 3.12 or later (tested with Python 3.12). Install the notebook dependencies in a virtual environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-notebook.txt
.venv/bin/python run_notebook.py
```

The final command executes all steps and saves the notebook with its outputs. For interactive
use, select that virtual environment as the notebook's Python kernel in your editor, or register it:

```sh
.venv/bin/python -m ipykernel install --user --name marketplace-assignment
```

Place `raw.sql` beside the notebook. Optional environment variables `RAW_SQL` and `OUTPUT_DIR`
select other paths; `MIN_GROUP` adjusts descriptive screening support and `HOLDOUT_FRACTION`
adjusts the chronological split. The defaults work on the supplied extract. Use a new output
directory when changing inputs or configuration to avoid stale optional charts from older runs.

`assignment_outputs/README.md` maps every CSV to its row meaning and inputs. The outputs include
raw/clean order records, change audits and quality flags, reconciliation checks, chart data and PNGs,
computed business findings, feature definitions, aligned features/IDs/nullable labels, training-only
preprocessing, edge-case test results, and scoped resource measurements.

The pipeline preserves the original SQL. Unknown outcomes remain unlabelled. No IDs or observed
counts are hardcoded into transformations. Dates in synthetic tests are examples, not cleaning rules.
ISO state codes, review-score ranges and unit conversions are documented domain rules.

The separate 6–8 page report and oral examination remain required by the brief. The notebook
provides the evidence and reproducible outputs needed to write that report; it does not fit a model.
