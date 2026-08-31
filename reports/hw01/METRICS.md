# METRICS.md

Results from `scripts/run_nondeterminism.py`, run against the fixed input in
`reports/hw01/cases/nondeterminism_input.json` (model: `qwen3:8b`, served locally via
Ollama, `reasoning`/`think` disabled). Raw per-run data: `reports/hw01/raw/nondeterminism_runs.csv`
and `.json`. Computed metrics: `reports/hw01/raw/nondeterminism_metrics.json`.

## Tag-set determinism

| Metric | Temp 0.7 | Temp 0.0 |
|---|---|---|
| Distinct tag sets | 19 | 1 |
| Tags in all 20 runs | (none) | "frozen blueberry packaging defect", "post-purchase product recall", "seal failure frost buildup" |
| Tags in exactly 1 run | 21 tags (see full list in `raw/nondeterminism_metrics.json`) | (none) |

## Latency

| Metric | Temp 0.7 | Temp 0.0 |
|---|---|---|
| Latency p50 (ms) | 42172.5 | 35940.0 |
| Latency p95 (ms) | 46518.6 | 38631.6 |
| Latency p99 (ms) | 49110.9 | 40311.9 |

## Interpretation

At **temperature 0.0**, the pipeline is essentially deterministic on this input: 20/20
runs produced the exact same 3 tags and (given the summary field wasn't compared here,
but was visually identical across the raw CSV) the same summary. Only sampling
randomness in the underlying decode should ever cause divergence at temp 0, and none was
observed in this run.

At **temperature 0.7**, only 1 out of 20 tag sets repeated (giving 19 distinct sets), no
tag survived in every run, and 21 different tag phrasings appeared in only one run each
-- the model reliably identifies the same 2-3 underlying concepts (packaging/seal
failure, frost buildup, recall) but phrases and combines them differently almost every
time.

Latency is also consistently higher at temp 0.7 (p50 42.2s vs 35.9s at temp 0.0, roughly
+17%) -- sampling-based decoding appears to take a modestly longer path than greedy
(temp 0.0) decoding for this model/prompt combination, though the effect is far smaller
than the effect on tag-set variability.

**What two users sending identical input might see:** at temp 0.0, two users submitting
the exact same recall title/content would get back the same 3 tags and summary --
useful whenever a user might reasonably expect "asking the same thing twice gives the
same answer" (e.g. two support agents independently triaging the same recall report and
expecting to file it under the same category). At temp 0.7, two users with identical
input would very likely get different tag phrasing each time (19/20 runs were unique) --
acceptable for a use case like generating draft tags a human then reviews/edits, but not
acceptable for something like automatically routing a recall to a fixed downstream
category/team purely off the tag text, since near-identical recalls could silently land
in different buckets run to run.
