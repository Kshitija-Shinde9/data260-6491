# AI_USE.md — DATA-260 HW8

## 1. What I used an AI assistant for, and what I did myself

I used AI when I got stuck with the syntax also to understand the concepts of the Kafka client, worker, and other new concepts. I created all the docker, the topic creates, the demo, the curl calls, and the Part 3 scripts. I also checked the terminal output before it went into the report.

## 2. One AI-produced output that was wrong or unsuitable

The Part 2 journey list printed only the heading. The programs showed each step on screen, but `reports/hw08/logs/part2_message_flow.log` was never created, so the journey under the heading was empty. The log path was being read once, at import time, while it was still empty.

## 3. How I detected the problem and verified the result

I grepped that path and got "No such file or directory." The four terminal windows still showed the planner, writer, and reviewer handing the same correlation id along, and the final JSON said status approved, so the pipeline itself had worked. The missing piece was only the file.

## 4. What I changed, and why it works now

`flow_log.py` now reads the log path when a line is written, not when the file is imported. I restarted the three agents and sent the question again. The journey then listed YOU, PLANNER, WRITER, REVIEWER, and YOU FINAL with one id, `2b83f4a7-e6f0-46cc-b334-4890d285daa4`.
