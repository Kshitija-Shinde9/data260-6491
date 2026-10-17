# AGENT.md

- Project description: s6491 is a grocery supply and recall notice assistant. It records product recalls and remembers facts from earlier conversations.
- Technology stack: the API is FastAPI, document memory is the MongoDB database s6491_doc, relational data is the MySQL database s6491_rel, and the local model is Ollama through src/model_client.py.
- Coding conventions: function names must describe the action they perform, and comments must not restate the code.
- Testing approach: check HTTP status codes and required fields rather than the exact wording of a model reply.
- Prohibited actions: never print or log a password, and never drop the notices collection.
