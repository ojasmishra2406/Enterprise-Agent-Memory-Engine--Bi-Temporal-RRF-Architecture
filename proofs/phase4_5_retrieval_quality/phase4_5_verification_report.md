# Phase 4.5: Retrieval Quality Hardening Verification Report

## TASK 4.5.1: Hybrid Retrieval Ablation
**Confirmed:** Hybrid search (using BGE-M3 dense embeddings) naturally outperformed sparse search on semantic variants ("What food does the user like?" vs "User loves tacos"), successfully ranking "tacos" at #1. 

*Raw Results for Query: "What food does the user like?"*
**Dense Only:**
Content: User loves tacos. | Distance: 0.2361
Content: User hates coffee. | Distance: 0.3720
Content: User went to Hawaii for vacation. | Distance: 0.4163
Content: Buddy is a golden retriever. | Distance: 0.5659

**Sparse Only:**
(0 hits - FTS failed entirely because "food/like" shares no stems with "loves/tacos")

**Hybrid RRF:**
Content: User loves tacos. | RRF Score: 0.0164 | Final: 0.0190
Content: User hates coffee. | RRF Score: 0.0161 | Final: 0.0187
Content: User went to Hawaii for vacation. | RRF Score: 0.0159 | Final: 0.0184
Content: Buddy is a golden retriever. | RRF Score: 0.0156 | Final: 0.0181


## TASK 4.5.2: Cross-Encoder Reranking
**Fixed:** Implementing a Cross-Encoder (`sentence-transformers/cross-encoder/ms-marco-MiniLM-L-6-v2`) successfully fixed the negation gap; "User loves tacos" now radically outscores "User hates coffee" (+3.24 vs -6.13).
**Confirmed:** The regression check proves the reranker perfectly preserved the retrieval accuracy of previously passing queries.

*Implementation (app/services/retrieval_service.py):*
```python
if _reranker is not None and len(results) > 0:
    start_t = time.perf_counter()
    pairs = [[req.query, r.content] for r in results]
    scores = _reranker.predict(pairs)
    for r, s in zip(results, scores):
        r.final_score = float(s)
    results.sort(key=lambda x: x.final_score, reverse=True)
```

*Raw Reranked Results:*
**Query: "What food does the user like?"**
Content: User loves tacos. | Final Score: 3.2429
Content: User hates coffee. | Final Score: -6.1325
Content: User went to Hawaii for vacation. | Final Score: -8.9060
Content: Buddy is a golden retriever. | Final Score: -10.9530

**Query: "Where did the user go on vacation?"**
Content: User went to Hawaii for vacation. | Final Score: 7.4450
Content: User loves tacos. | Final Score: -9.7555
Content: User hates coffee. | Final Score: -10.5875
Content: Buddy is a golden retriever. | Final Score: -11.3277

**Query: "What is the dog's name?"**
Content: Buddy is a golden retriever. | Final Score: -2.9262
Content: User loves tacos. | Final Score: -11.2339
Content: User hates coffee. | Final Score: -11.2510
Content: User went to Hawaii for vacation. | Final Score: -11.3508


## TASK 4.5.3: Reranking Latency Cost
**Confirmed:** The `ms-marco-MiniLM-L-6-v2` cross-encoder adds a negligible p50 latency of exactly 24.3 milliseconds (0.0243 seconds) to the retrieval pipeline across a 30-run sample inside the container.

*Raw Timing Output (30 runs):*
```text
p50 Reranking Latency: 0.0243 seconds
Mean Reranking Latency: 0.0247 seconds
```


## TASK 4.5.4: Time-Decay Validation
**Fixed/Confirmed:** Time decay successfully applies the exponential drop (`decay_rate = 2.67e-7/sec`) to monotonic effect, verifiable to six decimal places directly against the math at 1 day, 1 week, and 1 month.

*Method:* Backdated the memory's `valid_from` timestamp in PostgreSQL directly.
*Math formula:* `base_score * exp(-2.67e-7 * elapsed_seconds)`

*Raw Validation Results:*
**--- BASELINE (T=0) ---**
Base Score: 0.019016

**--- 1 Day (86,400s) ---**
Expected Math: 0.019016 * exp(-0.0230688) = 0.018583
Actual Score:   0.018583
Expected Score: 0.018583

**--- 1 Week (604,800s) ---**
Expected Math: 0.019016 * exp(-0.1614816) = 0.016181
Actual Score:   0.016181
Expected Score: 0.016181

**--- 1 Month (2,592,000s) ---**
Expected Math: 0.019016 * exp(-0.692064) = 0.009519
Actual Score:   0.009519
Expected Score: 0.009519
