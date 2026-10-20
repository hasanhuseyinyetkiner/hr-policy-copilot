# Evaluation results

Measured on the seeded synthetic corpus (`data/eval/questions.jsonl`).
Do not treat these as legal or production benchmarks.

**Method:** Recall@K / MRR / citation precision on seeded synthetic policies; faithfulness = sha256(snippet) match; abstention accuracy on unanswerable/ambiguous items; dense vs hybrid via retrieval_preference.

| Mode | Recall@4 | MRR | Citation precision | Faithfulness | Abstention accuracy |
| --- | --- | --- | --- | --- | --- |
| hybrid | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| dense | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
