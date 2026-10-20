# Evaluation results

Measured on the seeded synthetic corpus (`data/eval/questions.jsonl`), **n=11** questions.
Embedding backend for this run: `hash`. Do not treat these as legal advice or a production MiniLM benchmark.

**Method:** Recall@K / MRR / citation precision on seeded synthetic policies; faithfulness = sha256(snippet) match; abstention accuracy on unanswerable/ambiguous items; dense vs hybrid via retrieval_preference. Default runner uses the deterministic hash embedder (see scripts/run_eval.py).

| Mode | Recall@4 | MRR | Citation precision | Faithfulness | Abstention accuracy |
| --- | --- | --- | --- | --- | --- |
| hybrid | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| dense | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
