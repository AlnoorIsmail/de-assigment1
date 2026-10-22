"""Write the seven-page assignment discussion from the current pipeline outputs."""
from pathlib import Path
import json
import textwrap


def write_assignment_report(root):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    import pandas as pd
    from pipeline_support import read_frame

    root = Path(root)
    def read(stage, name):
        return read_frame(root / 'stages' / stage / (name + '.csv'))

    clean = read('08_cleaning', 'df_clean')
    orders = read('10_eda_window', 'df_labeled')
    audit = read('08_cleaning', 'order_audit')
    sensitivity = read('08_cleaning', 'sensitivity_df')
    states = read('11_eda_state', 'state_perf_filtered')
    state_sensitivity = read('08_cleaning', 'state_sensitivity')
    windows = read('10_eda_window', 'window_rates')
    delays = read('09_eda_delivery', 'delay_statistics').set_index('statistic')['days']
    local = read('12_eda_hypotheses', 'local_grouped')
    repairs = read('08_cleaning', 'item_repair_audit').set_index('Amount')
    feature_audit = read('08_cleaning', 'feature_audit_df')
    checks = json.loads((root / 'checks.json').read_text())
    resources = pd.read_csv(root / 'reports' / 'resources.csv')
    late = int(orders['delivered_after_estimate'].sum())
    rate = late / len(orders)
    biggest = states.sort_values('Late_Orders', ascending=False).head(2)
    top = states.iloc[0]
    unknown = int(orders['customer_state'].eq('unknown').sum())
    pages = []

    pages.append(('1. Business goal and data assembly', [
        'ENG2040 Assignment 1 | Alnoor Ismail | Marketplace orders and delivery outcomes',
        'The operations team needs to identify orders at risk of late delivery when approval occurs. '
        'This work produces cleaned records, reliable labels, descriptive findings and numerical inputs '
        'for a future model. It does not train a predictor or establish causal effects. The supplied '
        'data are a modified educational extract, so the findings apply to this extract rather than '
        'the original marketplace population.',
        f'The raw database contains {checks["assembled_orders"]:,} orders. Assembly preserves every order '
        'and creates one row per order. The cleaned table also retains every source order, including '
        f'uncertain outcomes. The main analytical cohort contains {len(orders):,} usable labeled orders. '
        'Order IDs remain separate from the feature matrix and link rows back to their source records.',
        'The orders table defines the observation. customer_id joins each order to its customer record; '
        'customer_unique_id identifies the same customer across orders. Each order_items row represents '
        'one purchased item, and order_item_id is its within-order sequence. Products, sellers and '
        'category translations enrich those item records. Payments are separate payment records, '
        'not one payment per installment. Reviews and shipment events are unavailable as predictors.',
        'Item records and payment records are aggregated independently before joining to orders. '
        'Joining both raw child tables directly would multiply item rows by payment rows and inflate '
        'counts and sums. LEFT JOIN retains orders whose child records are absent. Order IDs must '
        'remain unique, row counts must equal the source count, and aggregated item-price totals '
        'must match the source total before cleaning. Missing item amounts are later flagged rather '
        'than being silently accepted as reliable basket values.',
        'SQLite performs the main assembly close to the data. A matching Pandas implementation is '
        'used as an alternative. Both return the same columns and values before their timings are '
        'accepted. SQL is suitable for this modest local workload and avoids transferring every raw '
        'table into Python for the final aggregation. It is a measured implementation choice, not '
        'a universal claim that SQL is always faster.',
        'The raw assembly remains an audit view. selected_category and selected_payment_type contain '
        'the alphabetically last nonmissing values under SQL MAX. They are not dominant categories '
        'and are excluded from the final predictors. Descriptive payment comparisons therefore '
        'have a limited interpretation for orders with multiple payment types.'
    ]))

    counts = {col: int(audit[col].sum()) for col in
              ['anomaly_mask', 'chronology_mask', 'missing_outcome_mask', 'unknown_status_mask']}
    sensitivity_table = ['Policy                                      Orders   Late    Rate']
    for row in sensitivity.itertuples(index=False):
        sensitivity_table.append(f'{row.Policy[:43]:43} {row.Orders:6,d} {row.Late_Orders:6,d} {row.Late_Rate:7.2%}')
    pages.append(('2. Cleaning, labels and inclusion sensitivity', [
        'A label of 1 means delivery occurred after the estimated calendar date; delivery on that '
        'date is on time. Both timestamps are interpreted in the recorded local clock. No UTC '
        'offset is invented. Delay duration uses the difference between the two calendar dates, '
        'so every late delivery has at least one day of delay.',
        'Labels require delivered status, a purchase timestamp, delivery date and estimate, and no '
        'observed chronological contradictions. The checks compare purchase, approval, carrier and '
        'delivery timestamps wherever both are known. An estimate before the purchase or approval '
        'calendar date is also inconsistent. Missing optional approval or carrier timestamps alone '
        'do not prove the delivery outcome is unreliable; their uncertainty is retained.',
        'Missing or negative item prices/freight are checked before aggregation. Exact-product '
        'original valid medians repair prices; seller/destination-state original valid medians '
        'repair freight. Zero is valid. Missing matching keys and unmatched values stay missing. '
        'One unresolved item makes its corresponding repaired basket total unknown. Original '
        'amounts remain unchanged; no payment-ratio rule removes or alters large amounts.',
        f"Price: {int(repairs.loc['Price', 'Invalid Original']):,} invalid, "
        f"{int(repairs.loc['Price', 'Imputed']):,} repaired, "
        f"{int(repairs.loc['Price', 'Unresolved']):,} unresolved. Freight: "
        f"{int(repairs.loc['Freight', 'Invalid Original']):,} invalid, "
        f"{int(repairs.loc['Freight', 'Imputed']):,} repaired, "
        f"{int(repairs.loc['Freight', 'Unresolved']):,} unresolved.",
        f"All {len(orders):,} reliable deliveries enter EDA regardless of financial quality. "
        f"Features require items and complete repaired totals: {checks['feature_orders']:,} rows. "
        f"Among reliable deliveries, {int(feature_audit.iloc[1]['Dropped Rows']):,} have no items "
        f"and {int(feature_audit.iloc[2]['Dropped Rows']):,} have unresolved amounts. "
        'Optional catalogue missingness alone excludes neither population.',
        'Customer and seller states are trimmed and normalized before geographic features are '
        'calculated. Invalid states become unknown. An unknown location is not automatically '
        'cross-state fulfillment. Cleaned payment totals are divided by 100 to convert centavos '
        'to BRL; raw exports retain source units. The reconciliation reference is basket price plus '
        'freight, not basket price alone. Payments do not supply imputed predictors or determine outcome labels.',
        f'Overlapping source-order flags: {counts["anomaly_mask"]:,} have invalid/missing basket inputs; '
        f'{counts["chronology_mask"]:,} have chronology conflicts; {counts["missing_outcome_mask"]:,} lack '
        f'required outcome dates; {counts["unknown_status_mask"]:,} lack delivered status. These counts '
        'must not be added. order_audit.csv records each flag and final membership per original order.',
        ('table', '\n'.join(sensitivity_table)),
        'The date-only row is a diagnostic, not an acceptable final cohort. Comparing reliable outcomes '
        'with and without basket-quality restrictions shows the selection effect of requiring usable '
        'inputs. Missing-approval and missing-weight comparisons assess additional restrictions. '
        'These checks do not remove all selection bias: excluded and unobserved outcomes may differ '
        'systematically, so the main rate is conditional on inclusion.'
    ]))

    window_table = ['Approval-to-estimate days     Orders     Late     Late rate']
    for row in windows.itertuples(index=False, name=None):
        window_table.append(f'{str(row[0]):28} {int(row[1]):6,d} {int(row[2]):8,d} {row[3]:12.2%}')
    pages.append(('3. Business findings: lateness and promised windows', [
        f'Question 1: {late:,} of {len(orders):,} usable orders were late ({rate:.2%}). '
        f'The remaining {len(orders) - late:,} arrived on or before the estimated date. This is a '
        'completed, usable-order rate; it is not a delay rate for all placed orders. Cancelled, '
        'unknown and unreliable outcomes have not been reclassified as on-time deliveries.',
        f'Among late orders, the median delay was {delays["50%"]:.0f} calendar days and the mean was '
        f'{delays["mean"]:.2f} days. The 90th percentile was {delays["90%"]:.0f} days, the 95th was '
        f'{delays["95%"]:.0f}, and the maximum was {delays["max"]:.0f}. The mean exceeding the median '
        'indicates a right-skewed tail. The extreme delays merit individual review; deleting them '
        'merely because they are large would understate adverse outcomes.',
        'The outcome-count chart and delay histogram are saved in stages/09_eda_delivery. The '
        'histogram limits the displayed x-axis to the 99th percentile for readability, but its '
        'underlying CSV and the reported statistics retain all late orders. Display limits must '
        'not be confused with cleaning exclusions.',
        'Question 2: the promised window is estimated delivery date minus approval calendar date. '
        'Using calendar days avoids treating an estimate at midnight as a precise deadline earlier '
        'than approval on the same date. A missing approval timestamp means this window is unknown. '
        f'{orders["promised_window_days"].isna().sum():,} labeled orders are omitted from these window '
        'comparisons and are retained for other analyses.',
        ('table', '\n'.join(window_table)),
        'The shortest promise band has a high observed late rate in this extract. The relationship '
        'across longer bands is not a simple monotonic pattern. The outcome-specific box plot '
        'compares window distributions, while the table above directly compares late rates by '
        'promised window and exposes each denominator. Small bands support less precise estimates.',
        'Operationally, investigate whether short promises allow enough fulfillment time and whether '
        'their routes, products or sellers differ. This is an association, not evidence that changing '
        'the estimate would improve actual delivery speed. Promise lengths may already reflect '
        'distance or expected difficulty. Missing timestamps and cohort exclusions also limit '
        'generalization. The window sensitivity row on page 2 shows how complete approval records '
        'affect the overall rate.'
    ]))

    state_table = ['State     Orders    Late     Rate        bootstrap 95% interval']
    for row in states.head(8).itertuples(index=False):
        state_table.append(f'{row.customer_state.upper():5} {row.Total_Orders:9,d} {int(row.Late_Orders):7,d} '
                           f'{row.Late_Rate:9.2%}    {row.CI_Lower:.2%} to {row.CI_Upper:.2%}')
    rank_notes = []
    for policy in ['Main analysis: reliable outcomes', 'Complete original amounts', 'Repaired amounts: feature eligible']:
        part = state_sensitivity[(state_sensitivity['Policy'] == policy) &
                                 (state_sensitivity['customer_state'] != 'unknown') &
                                 (state_sensitivity['count'] >= 50)].sort_values('mean', ascending=False)
        rank_notes.append(policy + ': ' + ', '.join(part.head(3)['customer_state'].str.upper()))
    pages.append(('4. Business findings: geographic priorities', [
        'Question 3: customer-state comparisons use normalized valid state codes. Unknown geography '
        f'is reported separately ({unknown:,} usable orders) rather than being treated as a real '
        'state or silently discarded from the overall rate. The chart ranks valid states with at '
        'least 50 usable orders. This threshold limits very sparse displays; it is not proof of '
        'statistical reliability.',
        ('table', '\n'.join(state_table)),
        f'{top["customer_state"].upper()} has the highest displayed rate ({top["Late_Rate"]:.2%}), '
        f'based on {int(top["Total_Orders"]):,} orders. Its bootstrap interval is '
        f'{top["CI_Lower"]:.2%} to {top["CI_Upper"]:.2%}. Intervals overlap across several high-rate '
        'states, so the exact ranking should not be interpreted as a definitive ordering.',
        'Investigation should combine rate and impact. The two largest observed late-order counts '
        'among displayed states are ' + '; '.join(
            f'{r.customer_state.upper()}: {int(r.Late_Orders):,} late orders from {r.Total_Orders:,} '
            f'orders ({r.Late_Rate:.2%})' for r in biggest.itertuples(index=False)) + '. '
        'A high-volume state can offer more opportunities to reduce late deliveries even when its '
        'rate is below that of a smaller state.',
        'Top-three rates under alternative inclusion policies (same 50-order display rule):',
        ('table', '\n'.join(rank_notes)),
        'Compare state_sensitivity.csv for all states and policies. Stable high rates across '
        'defensible cohorts strengthen an investigation priority; changes in rank warn against '
        'overconfidence. Bootstrap intervals describe binomial sampling uncertainty only. They do not '
        'account for selective missingness, repeated customers, seller clustering, multiple state '
        'comparisons or the way this modified extract was assembled.',
        'A practical first review would examine high-rate states alongside the two high-volume '
        'states above, checking carrier routes, promise lengths, seller mix and excluded records. '
        'The data do not establish that customer location causes delays. Small states below the '
        'display cutoff still appear in the complete state table and should not be interpreted '
        'as having no delivery problems.'
    ]))

    feature_table = '''Feature / group                    Meaning and reason
Items, basket price, freight        Item count and repaired totals in BRL
log1p(price), log1p(freight)         Compress skew without discarding valid zeros
Freight / basket price             Relative shipping cost; unknown at zero price
Mean and maximum item weight       Typical and largest physical item; grams
Unique sellers, seller states      Sourcing complexity and geographic spread
Sellers / item count               Fraction of items from distinct sellers
Maximum photos                     Catalogue completeness proxy, not causation
Local seller flag                  Known seller/customer state match
Promised window                    Approval-to-estimate calendar days
Approval hour, weekend             Timing at approval; missing stays unknown
Weight/photo missing flags         Any item has missing optional information
Per-feature missing indicators     Preserve uncertainty after imputation
State one-hot columns              27 valid states plus explicit unknown'''
    pages.append(('5. Numerical features and leakage controls', [
        f'The final feature table has {checks["features"]} numerical columns and {checks["feature_orders"]:,} feature-eligible '
        'orders. It includes only basket, product, seller, customer-location and approval-time '
        'information permitted by the brief. Payments, final status, shipment and delivery events, '
        'reviews, shipping_limit_date, IDs and labels are excluded. Status and delivery dates are '
        'used only to establish reliable labels and inclusion, not as predictors.',
        ('table', feature_table),
        'Mean item weight is computed from item weights, not maximum weight divided by item count. '
        'It remains missing if any basket item weight is unknown, preventing a partial mean from '
        'masquerading as a complete-basket average. Maximum weight may use observed values, with '
        'a separate any-weight-missing flag. Unknown geography yields an unknown local-seller '
        'feature unless a known local match already establishes that at least one seller is local.',
        'Undefined freight/price ratios for valid zero-price baskets become missing instead of '
        'being divided by a tiny arbitrary number. Log transforms and fixed domain ratios do not '
        'learn from the target. State categories are fixed from the 27-state vocabulary plus '
        'unknown, keeping the representation consistent.',
        'The assignment produces one complete feature table with separate labels and order IDs. '
        'Unknown maximum photo counts use zero as a placeholder, retaining missing-photo flags. '
        'Other missing numerical values use medians from this prepared dataset. Entirely '
        'missing features use zero with a missing indicator. imputation_values.csv records the '
        'fill values, and X_unfilled.csv preserves the data before imputation. All final values '
        'must be finite, IDs unique, and the X/y/IDs rows aligned.',
        'These are baseline features chosen for meaning and availability, not demonstrated predictive '
        'importance. Some are redundant; later model evaluation should test whether they add value. '
        'No predictive evaluation is performed here. For future modeling, return to the original item records '
        'and refit both item-matching and predictor-fill medians on training data only. '
        'The appropriate evaluation design depends on the future deployment question.'

    ]))

    resource_table = ['Step                  Calc s (est/meas)   RSS MiB (est/meas)   Saved MiB (est/meas)']
    for row in resources.itertuples(index=False):
        resource_table.append(f'{row.stage[:21]:21} {row.estimated_calculation_seconds:6.2f}/{row.measured_calculation_seconds:<6.2f}'
                              f'  {row.estimated_peak_rss_bytes/1024**2:7.1f}/{row.measured_peak_rss_bytes/1024**2:<7.1f}'
                              f'   {row.estimated_saved_bytes/1024**2:6.2f}/{row.measured_saved_bytes/1024**2:<6.2f}')
    pages.append(('6. Reproducibility and resource use', [
        'After installing requirements.txt in the documented Python environment, run '
        'python run_pipeline.py. The runner rebuilds SQLite from raw.sql, calibrates estimates, '
        'executes every notebook stage, exports tables and chart data, validates results, runs '
        'equivalent benchmarks and writes both reports. Publication happens only after success. '
        'README.md maps stages to inputs, outputs, row meaning and loading instructions.',
        ('table', '\n'.join(resource_table)),
        'Estimates are recorded before full execution. A seeded SQL import sample estimates database '
        'creation, and up to 2,000 sampled orders with related records estimate notebook work. '
        'Row-dependent outputs scale by order count; fixed summaries and plot dimensions do not. '
        'Nonlinear joins, fixed plotting overhead and retained intermediates limit proportional '
        'runtime and memory predictions. Compare differences rather than treating estimates as '
        'capacity guarantees.',
        'RSS is sampled every 10 ms and includes native allocations and retained intermediates. '
        'Short spikes may be missed; maximum sample gaps are recorded. DataFrame deep memory is '
        'logical size, can double-count shared storage, and is separate from RSS. Temporary storage '
        'covers visible scratch and SQLite sidecar files, not hidden/unlinked files. Saved storage '
        'covers persistent stage artifacts. Full estimated/measured temporary, saved and intermediate '
        'storage plus calculation/export/inventory times are in reports/resources.csv and measurements.json.',
        'The companion assembly benchmark uses three fresh processes per approach, alternating '
        'execution order and checking equivalent values. Package imports and correctness checks '
        'are outside timing; filesystem caches are not flushed. reports/report.md records current '
        'medians, RSS and their interpretation. The notebook benchmark uses tracemalloc and must '
        'not be described as total physical RAM.',
        'The manifest includes checksums and dimensions. CSV schemas preserve types, IDs and nulls; '
        'read_frame restores them without guessing. Executed SQL, environment details and source '
        'snapshots are saved. Data outputs are deterministic in the documented environment; '
        'runtime, RSS and execution metadata naturally vary.'
    ]))

    local_notes = '; '.join(f'{r.fulfilment}: {r.Late_Rate:.2%} '
                           f'({r.Total_Orders:,} orders)' for r in local.itertuples(index=False))
    pages.append(('7. Interpretation, limitations and next steps', [
        f'The main operational result is a {rate:.2%} late-delivery rate among {len(orders):,} usable '
        f'completed orders, with a {delays["50%"]:.0f}-day median delay among late deliveries. '
        'Investigate short promises, high-rate states and high-volume sources of late orders '
        'together. The most useful priority is a combination of rate, affected order count, '
        'uncertainty and stability under alternative inclusion policies.',
        'Additional descriptive analyses examine product photos, selected payment type, local '
        'fulfillment, item weight and seller complexity. The local-fulfillment comparison is: '
        + local_notes + '. Unknown geography is its own group. Differences may reflect distance, '
        'route, basket or seller mix; they do not demonstrate that local fulfillment itself '
        'causes better performance.',
        'Photo counts may reflect catalogue completeness or product mix. Selected payment type is '
        'an alphabetically chosen descriptive summary, not a dominant method, and payment variables '
        'are excluded from predictors. Seller-count groups can be sparse. The weight scatter '
        'shows late orders below 50 kg and clips the displayed delay tail; it cannot estimate '
        'the risk of lateness across all orders. Large weights remain in analytical data, and '
        'display filters are documented rather than presented as cleaning decisions.',
        'Several limits remain. Unknown and unreliable outcomes cannot be assigned valid labels '
        'from the available records. Missing dates affect EDA selection; unresolved basket amounts '
        'further restrict features. Optional catalogue missingness is handled without automatic '
        'row loss, but median imputation does not recover the true values. Invalid geography is '
        'preserved as unknown, reducing the precision of geographic comparisons.',
        'The sensitivity table separates effects of outcome reliability, basket quality and '
        'optional completeness. State confidence intervals quantify only one source of uncertainty. '
        'The modified extract, repeated customers, seller clusters and unobserved operational '
        'factors limit stronger claims. No confidence interval establishes causality or guarantees '
        'that a pattern will persist in future orders.',
        'For a future model, fit preprocessing on training data and keep IDs/labels separate. Evaluate '
        'class-sensitive measures and calibration, then choose a decision threshold around '
        'operational costs. Use temporal validation if deployment targets future periods and '
        'customer grouping if the claim concerns unseen customers. Do not use final status or '
        'delivery events as approval-time predictors. No model performance is claimed here.',
        'References and evidence: assignment_01_brief.pdf (business definition, permitted inputs '
        'and Appendix B units); supplied data/raw.sql (modified Olist Brazilian E-Commerce Public '
        'Dataset, educational use, source licence CC BY-NC-SA 4.0); ENG2040_final.ipynb and its executed '
        'copy; exported stage tables and chart data; reports/report.md and resources.csv '
        '(measurement scope and benchmark evidence). All numerical findings above are regenerated '
        'from the current local extract.'
    ]))

    folder = root / 'reports'
    markdown = ['# ENG2040 Assignment 1 - Analysis report', '']
    with PdfPages(folder / 'assignment_report.pdf', metadata={'Title': 'ENG2040 Assignment 1', 'Author': 'Alnoor Ismail'}) as pdf:
        for number, (title, blocks) in enumerate(pages, 1):
            figure = plt.figure(figsize=(8.27, 11.69))
            figure.text(0.08, 0.95, title, fontsize=15, weight='bold', va='top')
            y = 0.905
            markdown.extend(['## ' + title, ''])
            for block in blocks:
                table = isinstance(block, tuple)
                content = block[1] if table else block
                lines = content.splitlines() if table else textwrap.wrap(content, width=100)
                size = 8.0 if table else 10.1
                spacing = 0.014 if table else 0.016
                if y - len(lines) * spacing < 0.055:
                    raise ValueError(f'Report page {number} is too long; shorten its discussion.')
                for line in lines:
                    figure.text(0.08, y, line, fontsize=size, va='top',
                                family='monospace' if table else 'sans-serif')
                    y -= spacing
                y -= 0.012
                markdown.extend((['```text', content, '```', ''] if table else [content, '']))
            figure.text(0.5, 0.03, f'ENG2040 | {number} / {len(pages)}', ha='center', fontsize=9)
            pdf.savefig(figure)
            plt.close(figure)
            markdown.extend(['<!-- page break -->', ''])
    (folder / 'assignment_report.md').write_text('\n'.join(markdown))
