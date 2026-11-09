# HW9 results

## Part 1. View counter

25 accesses of recall 1. Key `s6491:views:recall:1`.

| Check | Result |
|---|---|
| Redis count after 25 accesses | 25 |
| MySQL `view_count` | 20 |
| Database writes | access 10 and access 20 |

The database row updates when the Redis count is divisible by 10, so 25 in Redis and 20 in MySQL is the expected pair.

## Part 2. Semantic cache

12 questions: exact repeats, paraphrases, and new questions. Threshold 0.85.

| Measure | Result |
|---|---|
| Hits | 7 |
| Misses | 5 |
| Hit rate | 58.3% |
| Average latency, cached | 221.6 ms |
| Average latency, not cached | 5797.8 ms |

One exact repeat of the blueberry question hit at similarity 1.0000 in 31.3 ms. The first blueberry question missed and took 14631.7 ms.

False hit at threshold 0.85: "What is the recall type for Trader Joe's Organic Frozen Strawberries, 16oz?" returned the blueberry answer. Similarity 0.9292.

## Part 3. Threshold sweep

40 labeled cases in `reports/hw09/cache_cases.yaml`: 10 exact duplicates, 10 paraphrases, 10 superficial, 10 unrelated. Labels were not edited after the sweep.

Cost model, in relative units: a correct hit costs 0.2, a miss costs 8.0, a false hit costs 40.0.

| Threshold | Hit rate | False-hit rate | Mean latency (ms) | Total cost |
|---|---:|---:|---:|---:|
| 0.75 | 75.0% | 50.0% | 418.6 | 484.0 |
| 0.80 | 70.0% | 40.0% | 456.0 | 420.0 |
| 0.85 | 62.5% | 25.0% | 568.9 | 324.0 |
| 0.90 | 57.5% | 15.0% | 638.6 | 260.0 |
| 0.95 | 47.5% | 0.0% | 836.9 | 171.8 |

Shipped threshold: 0.95. Lowest total cost, 171.8, and a false-hit rate of 0.0%. Hit rate 47.5%. Mean latency 836.9 ms.

`para_08` is labeled as a paraphrase that should hit. It missed only at 0.95. The yaml file was left as labeled.

False hit shown in full, threshold 0.85, case `near_01`, group superficial.

| Field | Value |
|---|---|
| Cached query | What is the recall type for Trader Joe's Organic Frozen Blueberries, 16oz? |
| Incoming query | What is the recall type for Trader Joe's Organic Frozen Strawberries, 16oz? |
| Similarity | 0.9292 |
| Cached answer | Packaging / Seal Failure |
| Correct answer | No recall on file for strawberries |

Shared words: 16oz, for, frozen, is, joe's, organic, recall, the, trader, type, what. The change is strawberries.

Stale answer, `REC-0001` in `s6491_rel`.

| Step | data_version | Answer |
|---|---|---|
| Cached | 120@2026-11-09T20:56:54 | 120 units |
| Row updated | 300@2026-11-09T20:56:56 | cache still returned 120, similarity 1.0000 |
| After invalidation | 300@2026-11-09T20:56:56 | 300 units |
| Restored | 120@2026-11-09T20:57:00 | affected_units back to 120 |

Seed model calls averaged 3136.1 ms.

## Part 4. Two agents

`validation_data.json`, repair off.

| Stage | Correct | Incorrect | Average attempts | Average latency (ms) |
|---|---:|---:|---:|---:|
| Before the scoped lesson | 1 | 5 | 1.0 | 1643.5 |
| After the scoped lesson | 3 | 3 | 1.0 | 2108.0 |
| After the broad lesson | 1 | 5 | 1.0 | 3192.7 |

The scoped lesson was kept. The broad lesson was removed after the regression. `test_data.json` was loaded after that choice.

Held-out test, six questions, same file for every variant.

| Variant | Correct answers | Incorrect answers | Average attempts | Average latency (ms) |
|---|---:|---:|---:|---:|
| Baseline | 1 | 5 | 1.00 | 2741.3 |
| Evaluator Repair | 6 | 0 | 1.83 | 6931.5 |
| Lesson Memory | 2 | 4 | 1.00 | 4656.3 |
| Validated Improvement | 4 | 2 | 1.00 | 3304.5 |

