# Web Report input contract (Issue #223)

The public monthly report API is **read-only** and continues to require a valid,
scoped report token. Request shape:

`GET /api/public-reports/monthly/{token}[ /section/{section} | /export/{format} ]?period=month|week|today|custom&start=YYYY-MM-DD&end=YYYY-MM-DD&page=1`

## Period selection

- `month` (default): current **UTC** calendar month, inclusive.
- `week`: current UTC week from Monday through today, inclusive.
- `today`: today's UTC date.
- `custom`: **both** `start` and `end` are required, using strict
  Gregorian `YYYY-MM-DD`. The inclusive range is at most **366 days**
  (a leap-year-long interval is supported, a 367-day interval is not).
  Each date must be between **1900-01-01 and 2100-12-31**, inclusive. This
  envelope also protects previous-period comparisons and date arithmetic.
- As in the earlier API, reversed start/end are normalized by swapping them.
  The UI asks for start <= end. If `period` is not `custom`, previously
  selected start/end query fields are ignored (existing UI compatibility).
- Unknown period names, missing or malformed custom dates, and overly long
  spans fail **before any report query, export generation, or heatmap expansion**.

Limits apply uniformly to the dashboard summary, every section including
Heatmap, and full CSV/PDF exports. A 366-day export returns **all authorized**
rows matching that interval, not only one page; larger date ranges must be
split into several requests. Report visibility remains governed by the
separate Core authorization contract documented in
`docs/WEB_REPORT_TASK_VISIBILITY.md`.

## Paging

`page` is optional and defaults to 1; accepted values are ASCII decimal
integers between **1 and 10,000** inclusive. Leading zeroes are accepted.
Invalid numbers, negatives, zero, fractions, excessively long values, and
malformed percent-encoded values return HTTP 400. Existing pages (1-based,
25 rows per page) retain their behavior; an out-of-data but otherwise valid
page simply returns an empty page. Exports remain unpaginated.

Malformed query strings with more than 32 fields are also rejected with 400.

## Error response examples

All validation errors are HTTP 400 JSON bodies with one fixed safe code:
`invalid_report_period`, `invalid_report_date`,
`report_date_out_of_range`, `report_period_too_large`,
`invalid_report_page`, or `invalid_report_request`.
The API does not echo invalid inputs or internal exception text.

Invalid access tokens continue to return `report_not_found` (404) on valid
requests, and other unexpected report failures retain sanitized HTTP 500s.

## Decision/rationale

Previously custom dates were silently replaced by today when absent/invalid;
a huge range could generate arbitrarily many heatmap cells. Invalid `page`
was converted with `int()` before the route's error handler. Both defects
are real and independently reproducible. Bounded date spans and validated
paging prevent uncontrolled work while retaining full authorized annual
history through exports. The 366-day cap is a product safety contract, not a
claim about database row-count limits. Larger-history downloads, if needed,
should use separately paged/streamed archive functionality in a future issue.
