# LLM Extraction Contract

Use this contract for both fresh-context passes over one source file. Each pass receives the source independently and cannot see the other pass's result.

## Extraction JSON

Write one JSON object:

```json
{
  "schema_version": "finance-steward-llm-extraction-v1",
  "model": "openclaw-auto",
  "run_id": "fresh-unique-run-id",
  "source_sha256": "hex digest of the original file",
  "total_pages": 3,
  "reviewed_pages": [1, 2, 3],
  "transaction_count": 2,
  "complete": true,
  "uncertainties": [],
  "transactions": [
    {
      "transaction_date": "2026-08-01",
      "posted_date": null,
      "description": "SANITIZED MERCHANT",
      "amount_minor": -1234,
      "currency": "USD",
      "source_page": 2,
      "source_index": 1,
      "status": "posted"
    }
  ]
}
```

Only the listed keys are allowed. Use ISO dates and signed integer minor units. Positive values increase the selected account's signed balance; negative values decrease it. For a credit-card account, purchases are negative and payments or credits are positive.

`reviewed_pages` must equal every page from 1 through `total_pages`, in order. Count transaction rows, including identical legitimate purchases, not unique descriptions. Put concise transaction-specific ambiguity codes in `uncertainties`; never copy private statement text there.

The transaction schema deliberately has no balance, account, routing, person, address, or raw-text field. Sanitize long identifiers in descriptions as `[masked-id]` before writing JSON.

## Reconciliation

Run both passes in distinct sessions with distinct `run_id` values. The same available model may perform both passes. The staging script labels this `same_model_fresh_context`; it does not claim model independence.

The script matches records as a multiset of:

```text
transaction_date | amount_minor | currency | canonical description
```

It preserves repeated identical records. Any missing, extra, uncertainty, or duplicate dedupe key yields `needs_review`. Resolve only the discrepant records in another fresh session or with the owner; never silently choose one pass.

## Structured Exports

Use the same LLM contract for CSV, XLSX, OFX/QFX/QBO/QIF, and receipts. A runtime may use a deterministic reader as an optimization, but the portable skill does not depend on one and does not maintain per-bank parsing profiles.

## Acceptance Gate

Accept a file only when:

1. both passes bind to the original source SHA-256;
2. both report complete page coverage and distinct run IDs;
3. both transaction multisets match exactly;
4. neither pass reports uncertainty;
5. no dedupe-key collision remains unresolved;
6. the staging script returns `status=staged`.
