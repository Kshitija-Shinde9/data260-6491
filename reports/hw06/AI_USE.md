# AI_USE.md

## 1. What did you use an AI assistant for, and what did you do yourself?

I used an AI assistant when I got stuck on the memory parts. It helped me draft the MongoDB, the file-based commands, the consolidation logic. It also helped me to resolved the errors I got.

What I did myself: I setup the repo, set up MongoDB, and kept the FastAPI server and Ollama running. I sent the curl requests, looked at the collections in mongosh, and took the screenshots. I filled the Part 3 table from METRICS.md and checked the report against the assignment.

## 2. One AI-produced output that was wrong or unsuitable

The server command I was given was `uvicorn code.web_application.main:app` while I was already inside the `web_application` folder. It looked like the normal start command, but the server never came up.

## 3. How I detected the problem

I ran it and read the traceback. It ended with `ModuleNotFoundError: No module named 'code.web_application'; 'code' is not a package`. Python was picking up its own `code` module instead of my project folder, so the app never started.

## 4. What was changed and why it works now

From the `web_application` folder I started it with `uvicorn main:app --host 127.0.0.1 --port 8191`. The server stayed up after that, and the notice and chat requests started returning normal HTTP responses.
