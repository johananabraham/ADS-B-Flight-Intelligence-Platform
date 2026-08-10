# Dated FAA Safety Corpus Ingestion Evidence v1

## Executed proof

On 2026-08-10, the ingestion pipeline fetched the official eCFR Versioner API
artifacts for Title 14 Parts 61, 91, 121, and 135 effective 2026-07-24. Each source
was parsed and persisted in an isolated PostgreSQL container, then synchronized to
a separate Chroma corpus.

| Part | Bytes | Parsed sections | Rejected | Duplicates |
|---:|---:|---:|---:|---:|
| 61 | 640,036 | 149 | 0 | 0 |
| 91 | 806,139 | 286 | 0 | 0 |
| 121 | 1,198,306 | 390 | 0 | 0 |
| 135 | 673,764 | 200 | 0 | 0 |
| **Total** | **3,318,245** | **1,025** | **0** | **0** |

The checked-in JSON evidence records each exact URL, SHA-256, deterministic run ID,
and count. Identical reruns resolved to the same run IDs and reported
`applied: false`, proving the persistence path did not duplicate records.

## SQL-to-vector consistency

The corpus synchronization produced 1,025 expected and 1,025 indexed regulation
documents. Both the initial synchronization and a separate read-only check found:

- zero missing documents;
- zero orphan documents;
- zero source-lineage mismatches; and
- zero unversioned SQL rows.

## Evidence boundary

This is an executed local pipeline proof, not a production-data claim. It proves
dated FAA ingestion, idempotency, and SQL/vector lineage for four regulatory parts.
It does not prove retrieval quality outside the existing Part 91 evaluation, answer
faithfulness, or NTSB corpus completeness. The complete source XML is not checked
into this repository; the exact official URLs and hashes make the artifacts
identifiable and re-fetchable where the eCFR API retains that version.
