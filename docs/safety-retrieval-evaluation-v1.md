# FAA Part 91 Retrieval Evaluation v1

## Purpose

This evaluation measures whether semantic search returns the exact FAA regulation
section expected for a question. It does not ask an LLM to grade its own answer.

## Source and review boundary

The 15 cases in `evaluation/safety/faa_part91_retrieval_v1.json` were reviewed
against the official eCFR Title 14 Part 91 artifact effective 2026-07-24. The
dataset records its source URI, SHA-256, effective date, and parsed section count.
This is engineering review of an official source, not independent aviation-domain
expert review.

## Method

Each question is searched with a Part 91 metadata filter and top-K of five. The
runner compares ranked Chroma document IDs with the checked-in expected IDs and
calculates:

- Recall@3
- Recall@5
- mean reciprocal rank (MRR)
- machine-specific query latency

The baseline also records the embedding backend, distance function, HNSW
construction/search parameters, and top-K. A regression check fails closed when
the dataset, source artifact, retrieval configuration, Recall@3, or Recall@5 no
longer matches the baseline contract.

## Result

| Metric | Result |
|---|---:|
| Cases | 15 |
| Recall@3 | 0.9333 |
| Recall@5 | 0.9333 |
| MRR | 0.8111 |

One case remains outside the top five. Keeping that miss visible is intentional:
the baseline is evidence for future retrieval changes, not a claim of perfect
quality.

## Reproduce

First ingest the exact source artifact identified by the dataset into ChromaDB.
Then run:

```bash
PYTHONPATH=backend:. python3 scripts/run_safety_evaluation.py \
  --output /tmp/faa-part91-current.json \
  --baseline evaluation/results/faa_part91_retrieval_baseline_v1.json
```

The output is nonzero if Recall@3 or Recall@5 regresses or if the corpus or
retrieval configuration differs.

## Limits and next gates

This result does not measure NTSB narrative retrieval, structured SQL exact match,
citation precision/recall, answer faithfulness, cost, or production latency. Those
require an authorized NTSB data snapshot, reviewed ground truth, and a separate
synthesis rubric. No résumé or portfolio claim should imply those gates have
already passed.
