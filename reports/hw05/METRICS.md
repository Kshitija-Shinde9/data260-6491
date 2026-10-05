# HW5 Part 3 — Fault injection metrics

VERIFY_SEED = 266491
Tool under test = `search_recalls` (storage path with timeout + exponential backoff, max 3 attempts)
Calls = 50 per rate × 3 rates = 150 total

| Injected failure rate | Success rate | Mean latency (ms) | p99 latency (ms) |
|---|---|---|---|
| 0% | 100.0% | 2.33 | 50.57 |
| 20% | 100.0% | 17.45 | 162.11 |
| 50% | 92.0% | 40.43 | 163.31 |

