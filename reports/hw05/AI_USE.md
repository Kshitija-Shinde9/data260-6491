# AI_USE.md — DATA-260 HW5

## 1. What I used an AI assistant for, and what I did myself

I used chatgpt for help me: for guidance and clarification on a few technical components, including the Supplier/Recall models, FastAPI routers, execute_tool, I completed the implementation, testing, troubleshooting, and documentation by myslef, This included the MySQL migration, Postman CRUD testing, MCP Inspector screenshots, Redux UI checks, fault-injection tests, Ollama agent scenarios, and completed whole report with all screenshots by myslef.

## 2. One AI-produced output that was wrong or unsuitable

the older version of execute_tool.py failed to enforce the safety rule for searches using a submitter’s email address. it treated the request as a normal product search and returned ok: true with an empty result set. This was incorrect because the request should have been rejected before the normal search logic was executed.

## 3. How I detected the problem or verified the result

I ran scripts/demo_hw05_part5_safety.py and scripts/test_hw05_part4.py. The safety demo showed that the submitter email request was being reported as allowed instead of blocked. The test suite also showed that the expected safety error behavior was not being checked successfully. Comparing the files revealed that the Downloads copy still contained the Part 4 version of execute_tool.py, which did not include the Part 5 safety rule.

## 4. What I changed and why it works now

I replaced the outdated execute_tool.py with the Part 5 implementation, including the safety_violation handling, and added the corresponding safety checks to the test script. I then reran both the safety demo and the test suite. The protected request now returns ok: false with the required safety-error message instead of returning an empty successful result. The agent loop also uses the same SAFETY_ERROR constant from execute_tool.py, so the safety behavior is consistent across the live Ollama runs and the offline MockModel tests.