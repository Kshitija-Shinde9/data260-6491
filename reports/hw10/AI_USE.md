# AI_USE.md - DATA 260 HW10

## 1. What did you use AI for, and what did you do yourself?

I used AI when I got stuck or needed help understanding new topics. For this homework, I used it to better understand Streamlit, the automated evaluator, Spearman correlation, judge repeatability, tracing, and latency.

AI also helped me think about some errors and possible solutions. I tested the suggestions myself and only used the ones that worked with my project.

I did the main work myself. I created the dashboard, added the evaluator, created the evaluation cases, assigned the human labels, and ran the judge three times. I also ran the cache-hit, cache-miss, failed-trace, and 50-request latency tests. I checked the results and added the screenshots and explanations to the report myself.

## 2. One AI suggestion that was not suitable

One suggestion was to consider the judge reliable because it gave the same scores during all three runs. This was not enough to prove that the judge was accurate.

The judge gave the same scores each time, but its Spearman correlation with the human labels was -0.130. The mean absolute difference was 1.200. This showed that the judge was consistent but did not agree well with the human labels.

## 3. How did I find the problem?

I compared the judge scores with the human labels for all 20 cases. I checked the Spearman correlation, the mean absolute difference, and the individual scores for each case.

I also ran the same cases three times. The scores did not change, but the comparison with the human labels was still poor. This helped me understand that repeatability does not always mean that the judge is correct.

For the latency test, I ran 50 requests and checked the trace files to confirm that they were cache misses and went through the full pipeline.

## 4. What did I change, and why does it work?

I added the human labels, judge scores, correlation, mean absolute difference, and repeatability results to the dashboard and report.

I also added the same trace ID through the cache lookup, Kafka pipeline, evaluator, and final response. This allows the dashboard to show successful cache hits, cache misses, and failed requests.

The final results show that the dashboard and tracing are working. More testing with human-labeled examples needed before trusting it.