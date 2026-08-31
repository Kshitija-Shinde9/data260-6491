# AI_USE.md

## 1. What I used an AI assistant for, and what I did myself
I mainly used AI for the repetitive and boilerplate stuff in index.html, getting the basic structure of the JavaScript functions right, remembering exact Docker and AWS CLI command syntax, and formatting the JSON output nicely. It also helped me draft parts of DOMAIN_SCHEMA.md faster since that's mostly documentation.

## 2. One AI-produced output that was wrong/unsuitable
When I first got the Planner/Reviewer/Finalizer pipeline JSON output wasn't reliable. Sometimes it would return the tags and summary as flat keys like "data.tags" and "data.summary" instead of the nested structure. If I just ran 'json.loads()` directly on the raw response, it would either fail to parse or parse into a shape that didn't match what my code expected.

## 3. How I detected the problem / verified the result
I printed the raw model output to the console. I noticed sometimes the keys weren't nested the way my code expected. A couple of runs even threw errors when I tried to pull 'data["tags"]' because "data" didn't exist as a nested object, it was flattened. Seeing those raw outputs side by side made the pattern obvious.

## 4. What I changed, and why it works now
I wrote 'strip_code_and_md()' to strip out any thinking tags, and 'extract_json_block()' to pull out just the '{...}' portion of the text instead of assuming the whole response was clean JSON. Then I added 'coerce_reply() to normalize whatever shape came back, so if the model gave me flat keys instead of a nested "data" object, my code rebuilds the nested structure itself.

This works now because instead of assuming the model will always follow the JSON schema perfectly, my code assumes it might not and cleans up after it. That's also why the pipeline stayed stable across all 40 runs in the non-determinism test.
