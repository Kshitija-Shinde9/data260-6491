# METRICS.md - DATA-260 HW3
## Configuration

| | |
|---|---|
| SID4 | 6491 |
| PORT_BASE | 8191 |
| PREFIX | s6491 |
| SEED / VERIFY_SEED | 6491 / 266491 |
| DOMAIN_ID | 3 (grocery supply and recall notices) |
| Hardware | MacBook Air, Apple M4, 16 GB RAM |
| OS | macOS (Darwin 25.6.0) |
| Python | 3.11.16, conda environment `data260` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions, HuggingFace |
| Generative model | none - Part 2 is retrieval-only, `Settings.llm = None` |
| Corpus | 57 FDA documents, 395,149 bytes (385.9 KB) |
| Questions | 5, of which 4 are single-source |
| k | 5 |

## Chunker settings

| Technique | Class and settings |
|---|---|
| Token | `TokenTextSplitter(chunk_size=256, chunk_overlap=40)` |
| Semantic | `SemanticSplitterNodeParser(buffer_size=1, breakpoint_percentile_threshold=95)` |
| Sentence-window | `SentenceWindowNodeParser(window_size=3)` |

---

## 1. Retrieval quality

| Technique | Chunks | Avg chunk length | Top-1 cosine | Mean@k cosine | Recall@k | Mean retrieval latency (ms) |
|---|---|---|---|---|---|---|
| Token | 604 | 810.3 | 0.6456 | 0.5862 | 100% | 9.55 |
| Semantic | 205 | 1918.6 | 0.6322 | 0.5386 | 80% | 7.39 |
| Sentence window | 2525 | 155.8 | 0.6564 | 0.5508 | 100% | 24.48 |

### Chunking cost

| Technique | Chunks | Chunking time (ms) |
|---|---|---|
| Token | 604 | 315 |
| Semantic | 205 | 6357 |
| Sentence window | 2525 | 73 |

### Per question: was the expected source found in the top-5?

| Question | Token | Semantic | Sentence window |
|---|---|---|---|
| q1 potato chips / soy | rank 1, top1 0.694 | rank 1, top1 0.676 | rank 1, top1 0.687 |
| q2 Cabricharme cheese / egg | rank 1, top1 0.697 | rank 1, top1 0.687 | rank 1, top1 0.666 |
| q3 bettergoods pasta / Listeria | rank 3, top1 0.581 | rank 1, top1 0.587 | rank 1, top1 0.583 |
| q4 Everest & Maggi spices / Salmonella | rank 1, top1 0.626 | **NOT FOUND**, top1 0.604 | rank 1, top1 0.603 |
| q5 WanaBana puree / lead | rank 1, top1 0.629 | rank 1, top1 0.607 | rank 1, top1 0.741 |

---

## A confidently scored retrieval that does not contain the answer

| | |
|---|---|
| Expected source | `public_health_alert_concerning_recalled_everest_and_maggi_brand_spices.txt` |
| Returned at rank 1 | `public_health_advisories_investigations_foodborne_illness_outbreaks.txt` |
| store_score | 0.6069 |
| cosine_sim | 0.6040 |
| chunk length | 887 characters |
| Expected source anywhere in top-5? | No |

On q4 I asked which imported spice brands had Salmonella and who distributed them.
Semantic put this chunk at rank 1 with a score of 0.6069, which is confident, but it's
the wrong document and the right one didn't show up in the top 5 at all. The chunk it
gave me is just a list of outbreak headlines:

> "Listeria - Hispanic-style Cheeses Illnesses - Infused Rice Puffer Fish Poisoning
> Illness in Virginia Salmonella - Cashew Cheese from the Cultured Kitchen..."

Why it got fooled: that chunk is full of the same words as my question. Salmonella is in
there several times, plus recall and a bunch of imported foods. The embedding only knows
what a chunk is generally about, not which specific thing it names. What my question
actually needed was two names, Everest and Amin Trading Agency, and two words aren't
enough to beat a chunk that matches on everything else.

Semantic made it worse because its chunks are huge, 1,919 characters on average. So two
dozen unrelated outbreak titles got stuck together into one chunk, and that mix sits
close to pretty much any food contamination question. Token and sentence window both
found the right document at rank 1 for this same question.

---

## 2. Observations

For me, the context carried via the sentence window worked best. It put the right document at rank 1 for all five questions, while Token got four out of five and Semantic got four and missed one completely. I think this is because its chunks are tiny. When a recall notice says the thing you're looking for, that whole chunk is just that fact and nothing else.

You can see it on q5 where the sentence window scored 0.7412 and the other two only got 0.6290 and 0.6073. My corpus data is FDA recall notices, which are written in short plain sentences, and most of my questions are asking for one specific name like a brand or a distributor. So small chunks suit it.

Semantic did the worst and I think its own settings caused that. It only made 205 chunks and they were massive in length. On q4 it never found the actual spice alert at all. That chunk had loads of words like Salmonella and recall in it, so it looked similar, but it didn't contain the answer. It also had the lowest Mean@k cosine at 0.5386, so it wasn't just one bad question.

One thing I noticed is that the best technique wasn't the same every time. If you only look at the top 1 cosine, Token actually won three of the five questions, Semantic won q3 and sentence window won q5. Token also had the best Mean@k at 0.5862, so its medium sized chunks scored more evenly down the whole list, while sentence-window was higher at rank 1 but dropped off faster after that.


---

## 3. Conclusion

I think the sentence window is the best one for this corpus. It was the only technique that found the right document at rank 1 every single time, and it had the highest top-1 cosine at 0.6564. The downside is speed, since 2,525 chunks made searching take 24.48 ms compared to Token's 9.55 ms, although it was actually the fastest to chunk at only 73 ms versus Semantic's 6,357 ms.
Token is a really close second and honestly a safer pick if the corpus got much bigger, because it also got 100% Recall@5, had the best Mean@k at 0.5862, and was about two and a half times faster to search. I wouldn't use Semantic here, because it was the only one that missed a question, scored lowest on both cosine measures, and took twenty times longer to chunk than Token.


---

## How to reproduce

```bash
conda activate data260
pip install -r code/rag/requirements.txt

python code/rag/compare_chunking.py    # writes reports/hw03/raw/
python scripts/recompute_tables.py     # rebuilds every table above from raw/
python scripts/verify_hw03.py          # writes reports/hw03/verification.json
```
