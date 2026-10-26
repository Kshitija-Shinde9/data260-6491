# AI_USE.md — DATA-260 HW7

## 1. What I used an AI assistant for, and what I did myself
I used AI when I got stuck on Parts 5 and 6. It helped me understand the concepts behind the prompt defense and the file tools, track down errors, and talk through possible fixes. I wrote the requests, ran every script myself, decided which suggestions to keep, and took the screenshots. I also used it to draft some threat-model wording and format the report tables, and I checked that wording.

## 2. One AI-produced output that was wrong or unsuitable
The first Part 5 attempt ended up as a separate program instead of an extension of my existing app.py, so the same logic lived in two places. When I ran run_hw07_part5.py, it failed with a FileNotFoundError because reports/hw07/part4/scenarios/hostile_pricing.html wasn't in the scenarios folder.

## 3. How I detected the problem and verified the result
I compared the new file with my Part 4 app and saw the duplicated logic. The traceback named the missing fixture. After the fix, I reran run_hw07_part5.py and run_hw07_part6.py and checked the printed tables against what I expected, so I understood each step instead of just looking for a passing run.

## 4. What I changed, and why it works now
I changed Part 5 to call the same run_agent function from Part 4, so there is only one copy of that logic. The Part 5 runner now creates hostile_pricing.html if it's missing. For Part 6, I added the file tools and a safety gate to tools.py. To test the gate, I used a destructive command that begins with an allowed prefix, and it still got blocked, which shows the gate checks the whole command and not just the prefix. Working through these fixes helped me understand how the agent chooses tools.