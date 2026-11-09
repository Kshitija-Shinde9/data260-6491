# AI_USE.md - DATA 260 HW9

## 1. What I used an AI assistant for, and what I did myself

I used AI when I got stuck on the syntax and when I wanted to understand the new concepts like These were the Redis view counter that writes to the database every 10 views, the cosine similarity and the threshold, clearing the cache when a row changes, and the answering agent with an evaluator and a lesson memory. It also helped me find a few errors and talk through the fixes. I wrote all the scripts myself, picked the cost model and the threshold to ship, ran every part on my laptop, took the screenshots, and checked the terminal output against the tables before I put it in the report.

## 2. AI-produced outputs that were wrong or unsuitable
The first one was in Part 3. When I had to pick a threshold, the AI told me to use 0.85 because it had the best hit rate. It did not think about false hits costing more than a miss.
The second one was in Part 4. My scoped lesson was working, so I asked the AI to make a broader rule. It wrote "Always include 120 affected units and the Packaging / Seal Failure recall type in every answer." But those numbers are only right for one recall, so now the agent gave the blueberry answer to every question.

## 3. How I detected each problem and verified the fix
For Part 3, I did not just pick the best hit rate. I ran the sweep on all 40 cases and looked at the total cost, where a miss costs 8.0 and a false hit costs 40.0. At 0.85 the false-hit rate was 25% and the cost was 324.0. At 0.95 the false-hit rate was 0.0% and the cost was 171.8, which was the lowest, so I shipped 0.95. The false hit at 0.85 was real and I left it in the report: the strawberry question got the cached blueberry answer at similarity 0.9292.

For Part 4, I tested the broad lesson on `validation_data.json` before I kept it. The score dropped from 3 correct out of 6 to 1 correct out of 6, which is the same as having no lesson at all. So the broad rule made things worse and I removed it. The scoped lesson had raised the score from 1 to 3 on the same file, so I kept that one. I checked that `lessons.json` has `lesson_001` and not `lesson_002`, and I only opened `test_data.json` after I had made this choice.

## 4. What I changed, and what the AI wrote in Part 4

In Part 4 the AI suggested the draft answers, the evaluator feedback, and the two lesson corrections. I kept the scoped one, `lesson_001`, with the failure pattern "The answer omits the recall type." I removed the broad one, `lesson_002`, after it made the score drop. I did not change the labels in `cache_cases.yaml` or the questions in the data files after the runs. `para_08` is a paraphrase that should hit, and it only missed at 0.95, but I left it as it was instead of changing the label to make 0.95 look better. On the six test questions, Evaluator Repair got all 6 correct but took more attempts and time, and Validated Improvement got 4 correct. Working through the broad lesson that failed is what helped me understand this trade-off.
