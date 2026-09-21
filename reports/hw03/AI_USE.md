# AI_USE.md - DATA-260 HW3


## 1. What I used an AI assistant for, and what I did myself

What I used AI for - 
I used AI mostly for syntax I don't know off the top of my head, like the Bootstrap markup for my four Jinja templates and the LlamaIndex API, since I had never used SemanticSplitterNodeParser or SentenceWindowNodeParser before and needed to know what arguments they take.
I also used it to help pull down the FDA pages for my corpus, because the assignment needs 200 KB of local snapshots and doing fifty-odd pages by hand would have taken hours. The decisions were mine though. 

What I did by myself - 
I picked the chunker settings, read the documents and wrote all five expected answers before running anything, and decided how to define Recall@k since the assignment never says.
I also worked out that Starlette's session is stateless, so a copied cookie would still work after logout, and added a server-side session table in auth.py to fix that.

## 2. One AI-produced output that was wrong or unsuitable

For my environment screenshot I was told to run 'pip list | grep -E "llama-index|sentence-transformers|faiss|numpy|pandas"'. It only printed numpy 2.3.5 and pandas 2.3.3, meaning other packages were missing. My terminal prompt said (data260) so it looked like the right environment, but those version numbers weren't the ones I had just installed. If I had put that screenshot in my report it would have looked like four of the six required packages were never installed. Not just that but due to some misconfiguration in path and setup I had completely uninstall everything and install it again as their was some conflict when i was using python and new version of anaconda.

## 3. How I detected the problem and verified the result

I noticed the versions didn't match what pip had told me it installed a few minutes earlier, so instead of assuming I checked where the commands were actually pointing. 'which pip' gave /Library/Frameworks/Python.framework/Versions/3.13/bin/pip and 'which python' gave /opt/anaconda3/envs/data260/bin/python. So pip and python were two completely different interpreters, and bare pip was the system Python 3.13 even though my conda env was activated. That also explained something earlier in the homework, where 'pip install itsdangerous' said "Requirement already satisfied" but importing it still failed, because it was satisfied in the wrong Python.

## 4. What I changed, and why it works now

I switched to 'python -m pip' everywhere, both for installing and for listing. This works because '-m pip' runs pip as a module of whatever interpreter 'python' resolves to, so it can never end up targeting a different environment than the code I'm actually running. Now 'python -m pip list' shows all six required packages at the versions pinned in code/rag/requirements.txt. The general lesson is that output looking plausible isn't the same as it being right, and here the check that caught it was two 'which' commands.
