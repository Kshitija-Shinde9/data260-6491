# AI_USE.md

## 1. What did you use an AI assistant for, and what did you do yourself?

I used an AI assistant when I got stuck. It helped me check syntax, debugging, and parts of the implementation. That included help on the React pages, the Part 3 timing scripts and for part 4 to pick the six test questions, and organize the output files.

What I did myself: I reviewed the code, set up the project, and ran it myself. I had to setup the Python environment, Node, and MySQL, including the MySQL password. I took the Postman, MySQL, and browser screenshots. I filled in the Part 3 table from the measurement output. For Part 4, I ran the questions, read the retrieved chunks and answers, and compared No-RAG, Basic RAG, and Context-RAG. I also checked the assignment when the assistant was unsure.


## 2. One AI-produced output that was wrong or unsuitable

Two outputs looked fine at first and were not.

On the Home page, the search box looked connected, but the typed word was never sent to the backend. The page always showed the full list.

For Part 4, the first run used llama3.2:1b. On Q2, Context-RAG said it could not answer from the documents. The retrieved chunks already had the refrigerator temperature and the leftover time, so that refusal was wrong.


## 3. How I detected the problem

I did not catch the search bug by only reading the code. I tried it in the browser. I made a test record, typed part of its name, and still got all 4 records instead of 1.

For Q2, I read the retrieval printout before the answer. The log showed the source, the score, and chunk text with 40°F and 2 hours. The refusal did not match that text, so the problem was the search, not the model.


## 4. What was changed and why it works now

I changed fetchRecalls() so it takes the search text and adds it to the request as ?search=. The backend already had that filter. I tried the same search again in the browser, and it returned 1 record instead of 4.

For Part 4, I ran the same questions with llama3.2:3b. Q2 then used the chunks and included both facts. Q5 and Q6 still used the required refusal, because those answers are not in the documents. Reading the printed chunks separately from the answer is what showed the difference.