# AI_USE.md - DATA-260 HW2


## 1. What I used an AI assistant for, and what I did myself
I used the local model (qwen3:8b through Ollama) to actually run as my Planner and Reviewer inside the LangGraph pipeline, that's just what the assignment needed. I also used AI to help me remember syntax stuff, like FastAPI routes, Pydantic validators. But I wrote the actual logic myself, the router, the supervisor node, the AgentState fields, and the schema rules.

## 2. One AI-produced output that was wrong or unsuitable

When I first started running the Planner and Reviewer nodes, the model's raw replies weren't clean JSON. Sometimes it would wrap the answer in thinking tags or add code fences around it, and sometimes the tags list would come back with the wrong number of tags, like two instead of three, or it would leave out the summary field completely. If I just ran json.loads() straight on the raw text, it either crashed or gave me a shape that didn't match what my AgentState expected.

## 3. How I detected the problem and verified the result

I built a separate test file called try_schema.py that checked my Pydantic rules against one good example and five bad ones on purpose, things like too few tags, tags that were too short, and summaries that were too long. Running that script showed me exactly which rule each bad example broke, which confirmed my validation logic worked correctly. Then when I ran the real Planner and Reviewer nodes on an actual recall notice, I compared the model's raw text output against what my schema expected and saw the mismatch happening live, the model's reply had extra text around the JSON, and it needed to be cleaned before validation would even accept it.


## 4. What I changed, and why it works now

The problem was that I never told the Reviewer what my schema rules actually were, so it kept asking for stuff that was literally impossible to give it. I added the real limits into the Reviewer's prompt: exactly three tags, three to thirty characters each, summary under twenty five words. Once the Reviewer knew its own feedback had to stay inside those limits, it stopped demanding things the Planner couldn't do, and the loop stopped. This fixed the actual cause instead of just working around it.
