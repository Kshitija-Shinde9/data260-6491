# HW8 results

SID4 6491. PREFIX s6491. SEED 6491. VERIFY_SEED 266491. Broker on this Mac is localhost:9094.

The numbers below are the runs in the report screenshots. The 20-message list is `reports/hw08/raw/ordering_messages.json`. The two ordering tables are `reports/hw08/raw/ordering_run.json`. The other three Part 3 cases are `reports/hw08/raw/part3_failure_cases.json`.

## Failure table

| Failure scenario | Before fix | After fix |
|---|---|---|
| Duplicate delivery | `dup-266491` sent twice, idempotency off. Two SEND lines. | Same id, idempotency on. One SEND, then DUPLICATE, no second draft. |
| Consumer killed mid-work | `crash-before-266491`. COMMIT, then CRASH. Restart said redelivered = no. | `crash-after-266491`. CRASH before COMMIT. Restart did RECEIVE, SEND, COMMIT. redelivered = yes. |
| Poison message | No retry limit and no dead-letter topic, so `good-266491` would never be drafted. | `poison-266491` tried 3 times, moved to `s6491_dead_letter`, attempts = 3. `good-266491` was drafted after it. |
| Two partitions / two consumers | No product key. All four products landed on partitions 0 and 1, and processed order did not match sent order. | Key = product name. All four products stayed on partition 0, and processed order matched sent order. |

## Ordering, VERIFY_SEED 266491

20 messages, 4 products, 5 updates each, 2 writers, topic `s6491_tasks` with 2 partitions.

| Product | Run 1 partitions | Run 1 sent | Run 1 processed | Run 2 partitions | Run 2 sent | Run 2 processed |
|---|---|---|---|---|---|---|
| blueberries | 0,1 | 0 4 1 2 3 | 0 3 4 1 2 | 0 | 0 4 1 2 3 | 0 4 1 2 3 |
| chicken | 0,1 | 0 3 1 2 4 | 1 2 0 3 4 | 0 | 0 3 1 2 4 | 0 3 1 2 4 |
| trail mix | 0,1 | 2 3 4 1 0 | 2 3 1 4 0 | 0 | 2 3 4 1 0 | 2 3 4 1 0 |
| spinach | 0,1 | 4 0 2 1 3 | 0 2 3 4 1 | 0 | 4 0 2 1 3 | 4 0 2 1 3 |

Run 1: a product landed on both partitions: yes.
Run 2: every product stayed on one partition, in the order it was sent: yes.

## Part 1 and Part 2 ids from the same report

| Run | correlation_id | Result |
|---|---|---|
| Part 1 demo CREATE/GET | daaf6214-0b06-4e54-a35f-2cc369cd1d51 | recall_id a882f870-0c0b-48c6-8def-20a7645ca886, preserved = True |
| Part 1 API curl | fab236e9-39bc-4d15-876e-f078c07960a9 | HTTP 201, recall_id 2c261c67-2383-4ba1-96a3-665b60897039, GET 200 |
| Part 2 final answer | 2b83f4a7-e6f0-46cc-b334-4890d285daa4 | status approved, correlation_id preserved = True |
