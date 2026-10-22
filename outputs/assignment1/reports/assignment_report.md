# ENG2040 Assignment 1 - Analysis report

## 1. Business goal and data assembly

ENG2040 Assignment 1 | Alnoor Ismail | Marketplace orders and delivery outcomes

The operations team needs to identify orders at risk of late delivery when approval occurs. This work produces cleaned records, reliable labels, descriptive findings and numerical inputs for a future model. It does not train a predictor or establish causal effects. The supplied data are a modified educational extract, so the findings apply to this extract rather than the original marketplace population.

The raw database contains 20,000 orders. Assembly preserves every order and creates one row per order. The cleaned table also retains every source order, including uncertain outcomes. The main analytical cohort contains 15,940 usable labeled orders. Order IDs remain separate from the feature matrix and link rows back to their source records.

The orders table defines the observation. customer_id joins each order to its customer record; customer_unique_id identifies the same customer across orders. Each order_items row represents one purchased item, and order_item_id is its within-order sequence. Products, sellers and category translations enrich those item records. Payments are separate payment records, not one payment per installment. Reviews and shipment events are unavailable as predictors.

Item records and payment records are aggregated independently before joining to orders. Joining both raw child tables directly would multiply item rows by payment rows and inflate counts and sums. LEFT JOIN retains orders whose child records are absent. Order IDs must remain unique, row counts must equal the source count, and aggregated item-price totals must match the source total before cleaning. Missing item amounts are later flagged rather than being silently accepted as reliable basket values.

SQLite performs the main assembly close to the data. A matching Pandas implementation is used as an alternative. Both return the same columns and values before their timings are accepted. SQL is suitable for this modest local workload and avoids transferring every raw table into Python for the final aggregation. It is a measured implementation choice, not a universal claim that SQL is always faster.

The raw assembly remains an audit view. selected_category and selected_payment_type contain the alphabetically last nonmissing values under SQL MAX. They are not dominant categories and are excluded from the final predictors. Descriptive payment comparisons therefore have a limited interpretation for orders with multiple payment types.

<!-- page break -->

## 2. Cleaning, labels and inclusion sensitivity

A label of 1 means delivery occurred after the estimated calendar date; delivery on that date is on time. Both timestamps are interpreted in the recorded local clock. No UTC offset is invented. Delay duration uses the difference between the two calendar dates, so every late delivery has at least one day of delay.

Labels require delivered status, a purchase timestamp, delivery date and estimate, and no observed chronological contradictions. The checks compare purchase, approval, carrier and delivery timestamps wherever both are known. An estimate before the purchase or approval calendar date is also inconsistent. Missing optional approval or carrier timestamps alone do not prove the delivery outcome is unreliable; their uncertainty is retained.

Missing or negative item prices/freight are checked before aggregation. Exact-product original valid medians repair prices; seller/destination-state original valid medians repair freight. Zero is valid. Missing matching keys and unmatched values stay missing. One unresolved item makes its corresponding repaired basket total unknown. Original amounts remain unchanged; no payment-ratio rule removes or alters large amounts.

Price: 847 invalid, 538 repaired, 309 unresolved. Freight: 885 invalid, 644 repaired, 241 unresolved.

All 15,940 reliable deliveries enter EDA regardless of financial quality. Features require items and complete repaired totals: 15,505 rows. Among reliable deliveries, 0 have no items and 435 have unresolved amounts. Optional catalogue missingness alone excludes neither population.

Customer and seller states are trimmed and normalized before geographic features are calculated. Invalid states become unknown. An unknown location is not automatically cross-state fulfillment. Cleaned payment totals are divided by 100 to convert centavos to BRL; raw exports retain source units. The reconciliation reference is basket price plus freight, not basket price alone. Payments do not supply imputed predictors or determine outcome labels.

Overlapping source-order flags: 1,845 have invalid/missing basket inputs; 1,061 have chronology conflicts; 1,521 lack required outcome dates; 2,070 lack delivered status. These counts must not be added. order_audit.csv records each flag and final membership per original order.

```text
Policy                                      Orders   Late    Rate
Dates present only (not reliable)           18,479  1,190   6.44%
Main analysis: reliable outcomes            15,940  1,083   6.79%
Complete original amounts                   14,580  1,007   6.91%
Repaired amounts: feature eligible          15,505  1,065   6.87%
Main analysis, approval recorded            15,629  1,058   6.77%
Main analysis, all item weights recorded    14,724  1,003   6.81%
```

The date-only row is a diagnostic, not an acceptable final cohort. Comparing reliable outcomes with and without basket-quality restrictions shows the selection effect of requiring usable inputs. Missing-approval and missing-weight comparisons assess additional restrictions. These checks do not remove all selection bias: excluded and unobserved outcomes may differ systematically, so the main rate is conditional on inclusion.

<!-- page break -->

## 3. Business findings: lateness and promised windows

Question 1: 1,083 of 15,940 usable orders were late (6.79%). The remaining 14,857 arrived on or before the estimated date. This is a completed, usable-order rate; it is not a delay rate for all placed orders. Cancelled, unknown and unreliable outcomes have not been reclassified as on-time deliveries.

Among late orders, the median delay was 7 calendar days and the mean was 10.51 days. The 90th percentile was 22 days, the 95th was 29, and the maximum was 188. The mean exceeding the median indicates a right-skewed tail. The extreme delays merit individual review; deleting them merely because they are large would understate adverse outcomes.

The outcome-count chart and delay histogram are saved in stages/09_eda_delivery. The histogram limits the displayed x-axis to the 99th percentile for readability, but its underlying CSV and the reported statistics retain all late orders. Display limits must not be confused with cleaning exclusions.

Question 2: the promised window is estimated delivery date minus approval calendar date. Using calendar days avoids treating an estimate at midnight as a precise deadline earlier than approval on the same date. A missing approval timestamp means this window is unknown. 311 labeled orders are omitted from these window comparisons and are retained for other analyses.

```text
Approval-to-estimate days     Orders     Late     Late rate
0-7                             282       48       17.02%
8-14                          1,883       94        4.99%
15-21                         4,005      283        7.07%
22-28                         5,527      421        7.62%
29+                           3,932      212        5.39%
```

The shortest promise band has a high observed late rate in this extract. The relationship across longer bands is not a simple monotonic pattern. The outcome-specific box plot compares window distributions, while the table above directly compares late rates by promised window and exposes each denominator. Small bands support less precise estimates.

Operationally, investigate whether short promises allow enough fulfillment time and whether their routes, products or sellers differ. This is an association, not evidence that changing the estimate would improve actual delivery speed. Promise lengths may already reflect distance or expected difficulty. Missing timestamps and cohort exclusions also limit generalization. The window sensitivity row on page 2 shows how complete approval records affect the overall rate.

<!-- page break -->

## 4. Business findings: geographic priorities

Question 3: customer-state comparisons use normalized valid state codes. Unknown geography is reported separately (1,637 usable orders) rather than being treated as a real state or silently discarded from the overall rate. The chart ranks valid states with at least 50 usable orders. This threshold limits very sparse displays; it is not proof of statistical reliability.

```text
State     Orders    Late     Rate        bootstrap 95% interval
MA          116      21    18.10%    12.16% to 26.10%
CE          181      32    17.68%    12.81% to 23.89%
AL           70      12    17.14%    10.09% to 27.62%
PE          223      35    15.70%    11.51% to 21.05%
PI           72      11    15.28%    8.75% to 25.32%
BA          490      59    12.04%    9.45% to 15.22%
RJ        1,873     216    11.53%    10.16% to 13.06%
PA          135      15    11.11%    6.85% to 17.52%
```

MA has the highest displayed rate (18.10%), based on 116 orders. Its bootstrap interval is 12.16% to 26.10%. Intervals overlap across several high-rate states, so the exact ranking should not be interpreted as a definitive ordering.

Investigation should combine rate and impact. The two largest observed late-order counts among displayed states are SP: 275 late orders from 5,998 orders (4.58%); RJ: 216 late orders from 1,873 orders (11.53%). A high-volume state can offer more opportunities to reduce late deliveries even when its rate is below that of a smaller state.

Top-three rates under alternative inclusion policies (same 50-order display rule):

```text
Main analysis: reliable outcomes: MA, CE, AL
Complete original amounts: CE, MA, AL
Repaired amounts: feature eligible: CE, MA, AL
```

Compare state_sensitivity.csv for all states and policies. Stable high rates across defensible cohorts strengthen an investigation priority; changes in rank warn against overconfidence. Bootstrap intervals describe binomial sampling uncertainty only. They do not account for selective missingness, repeated customers, seller clustering, multiple state comparisons or the way this modified extract was assembled.

A practical first review would examine high-rate states alongside the two high-volume states above, checking carrier routes, promise lengths, seller mix and excluded records. The data do not establish that customer location causes delays. Small states below the display cutoff still appear in the complete state table and should not be interpreted as having no delivery problems.

<!-- page break -->

## 5. Numerical features and leakage controls

The final feature table has 53 numerical columns and 15,505 feature-eligible orders. It includes only basket, product, seller, customer-location and approval-time information permitted by the brief. Payments, final status, shipment and delivery events, reviews, shipping_limit_date, IDs and labels are excluded. Status and delivery dates are used only to establish reliable labels and inclusion, not as predictors.

```text
Feature / group                    Meaning and reason
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
State one-hot columns              27 valid states plus explicit unknown
```

Mean item weight is computed from item weights, not maximum weight divided by item count. It remains missing if any basket item weight is unknown, preventing a partial mean from masquerading as a complete-basket average. Maximum weight may use observed values, with a separate any-weight-missing flag. Unknown geography yields an unknown local-seller feature unless a known local match already establishes that at least one seller is local.

Undefined freight/price ratios for valid zero-price baskets become missing instead of being divided by a tiny arbitrary number. Log transforms and fixed domain ratios do not learn from the target. State categories are fixed from the 27-state vocabulary plus unknown, keeping the representation consistent.

The assignment produces one complete feature table with separate labels and order IDs. Unknown maximum photo counts use zero as a placeholder, retaining missing-photo flags. Other missing numerical values use medians from this prepared dataset. Entirely missing features use zero with a missing indicator. imputation_values.csv records the fill values, and X_unfilled.csv preserves the data before imputation. All final values must be finite, IDs unique, and the X/y/IDs rows aligned.

These are baseline features chosen for meaning and availability, not demonstrated predictive importance. Some are redundant; later model evaluation should test whether they add value. No predictive evaluation is performed here. For future modeling, return to the original item records and refit both item-matching and predictor-fill medians on training data only. The appropriate evaluation design depends on the future deployment question.

<!-- page break -->

## 6. Reproducibility and resource use

After installing requirements.txt in the documented Python environment, run python run_pipeline.py. The runner rebuilds SQLite from raw.sql, calibrates estimates, executes every notebook stage, exports tables and chart data, validates results, runs equivalent benchmarks and writes both reports. Publication happens only after success. README.md maps stages to inputs, outputs, row meaning and loading instructions.

```text
Step                  Calc s (est/meas)   RSS MiB (est/meas)   Saved MiB (est/meas)
00_database             0.37/0.29      258.7/202.6      23.20/23.23 
01_setup               23.41/37.77     205.0/209.3       0.00/0.00  
02_inspection           0.28/0.04      228.9/214.0       0.01/0.01  
03_multiplicity         0.09/0.02      233.0/217.4       0.00/0.00  
04_preservation         0.24/0.11      267.1/230.2       0.00/0.00  
05_assembly             0.40/0.29      368.8/297.8       5.21/5.22  
06_original_benchmark  15.32/15.76     546.8/439.6      10.46/10.48 
07_profile              0.72/0.29      553.5/444.1       0.01/0.01  
08_cleaning             6.39/5.23      675.7/495.6      20.51/20.50 
09_eda_delivery         4.62/0.50      710.5/510.1       5.93/5.93  
10_eda_window          17.12/1.90      898.8/530.1       6.86/6.85  
11_eda_state            2.99/0.39      971.3/530.2       0.05/0.07  
12_eda_hypotheses       6.89/0.73     1066.3/530.2       0.12/0.11  
13_eda_weight           2.71/0.32     1082.4/530.4       0.06/0.11  
14_eda_sellers          1.87/0.20     1112.2/530.5       0.04/0.04  
15_initial_features     0.13/0.03     1154.6/554.1       6.26/6.35  
16_final_features       0.32/0.04     1331.6/597.1      15.42/15.65 
17_resources            0.16/0.06     1331.6/597.1       0.00/0.00  
```

Estimates are recorded before full execution. A seeded SQL import sample estimates database creation, and up to 2,000 sampled orders with related records estimate notebook work. Row-dependent outputs scale by order count; fixed summaries and plot dimensions do not. Nonlinear joins, fixed plotting overhead and retained intermediates limit proportional runtime and memory predictions. Compare differences rather than treating estimates as capacity guarantees.

RSS is sampled every 10 ms and includes native allocations and retained intermediates. Short spikes may be missed; maximum sample gaps are recorded. DataFrame deep memory is logical size, can double-count shared storage, and is separate from RSS. Temporary storage covers visible scratch and SQLite sidecar files, not hidden/unlinked files. Saved storage covers persistent stage artifacts. Full estimated/measured temporary, saved and intermediate storage plus calculation/export/inventory times are in reports/resources.csv and measurements.json.

The companion assembly benchmark uses three fresh processes per approach, alternating execution order and checking equivalent values. Package imports and correctness checks are outside timing; filesystem caches are not flushed. reports/report.md records current medians, RSS and their interpretation. The notebook benchmark uses tracemalloc and must not be described as total physical RAM.

The manifest includes checksums and dimensions. CSV schemas preserve types, IDs and nulls; read_frame restores them without guessing. Executed SQL, environment details and source snapshots are saved. Data outputs are deterministic in the documented environment; runtime, RSS and execution metadata naturally vary.

<!-- page break -->

## 7. Interpretation, limitations and next steps

The main operational result is a 6.79% late-delivery rate among 15,940 usable completed orders, with a 7-day median delay among late deliveries. Investigate short promises, high-rate states and high-volume sources of late orders together. The most useful priority is a combination of rate, affected order count, uncertainty and stability under alternative inclusion policies.

Additional descriptive analyses examine product photos, selected payment type, local fulfillment, item weight and seller complexity. The local-fulfillment comparison is: Unknown Geography: 6.25% (3,056 orders); Cross-State Only: 8.19% (8,136 orders); Involves Local Seller: 4.76% (4,748 orders). Unknown geography is its own group. Differences may reflect distance, route, basket or seller mix; they do not demonstrate that local fulfillment itself causes better performance.

Photo counts may reflect catalogue completeness or product mix. Selected payment type is an alphabetically chosen descriptive summary, not a dominant method, and payment variables are excluded from predictors. Seller-count groups can be sparse. The weight scatter shows late orders below 50 kg and clips the displayed delay tail; it cannot estimate the risk of lateness across all orders. Large weights remain in analytical data, and display filters are documented rather than presented as cleaning decisions.

Several limits remain. Unknown and unreliable outcomes cannot be assigned valid labels from the available records. Missing dates affect EDA selection; unresolved basket amounts further restrict features. Optional catalogue missingness is handled without automatic row loss, but median imputation does not recover the true values. Invalid geography is preserved as unknown, reducing the precision of geographic comparisons.

The sensitivity table separates effects of outcome reliability, basket quality and optional completeness. State confidence intervals quantify only one source of uncertainty. The modified extract, repeated customers, seller clusters and unobserved operational factors limit stronger claims. No confidence interval establishes causality or guarantees that a pattern will persist in future orders.

For a future model, fit preprocessing on training data and keep IDs/labels separate. Evaluate class-sensitive measures and calibration, then choose a decision threshold around operational costs. Use temporal validation if deployment targets future periods and customer grouping if the claim concerns unseen customers. Do not use final status or delivery events as approval-time predictors. No model performance is claimed here.

References and evidence: assignment_01_brief.pdf (business definition, permitted inputs and Appendix B units); supplied data/raw.sql (modified Olist Brazilian E-Commerce Public Dataset, educational use, source licence CC BY-NC-SA 4.0); ENG2040_final.ipynb and its executed copy; exported stage tables and chart data; reports/report.md and resources.csv (measurement scope and benchmark evidence). All numerical findings above are regenerated from the current local extract.

<!-- page break -->
