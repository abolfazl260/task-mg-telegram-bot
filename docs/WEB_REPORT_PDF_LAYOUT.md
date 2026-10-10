# Web Report PDF export layout contract — Issue #227

## Confirmed defects in the previous implementation

The earlier canvas renderer used a fixed `12 pt` row pitch with seven fixed
column x-coordinates. Every cell was cut to `str(value)[:30]`, regardless
of its rendered width. Titles and identifiers could therefore extend over
adjacent columns. When the page ended, the code called `showPage()` and
continued drawing rows at a new y coordinate, **without repeating the
table's headings or any report period context**. The fallback Helvetica
font does not support Persian glyphs. The PDF smoke test checked only the
`%PDF` prefix and could not detect these problems.

## New layout

- Landscape A4 with a 28 pt horizontal margin, seven **right-to-left**
  columns and consistent column widths.
- A Unicode-capable font (DejaVu Sans, Noto Naskh Arabic, FreeSerif or a
  suitable platform fallback) is embedded in PDF. If the server lacks
  a usable font, export fails explicitly rather than returning unreadable
  Persian. Install `fonts-dejavu-core` (or Noto Arabic/FreeSerif) in the
  deployment image.
- Mixed Persian/English cells use existing Arabic shaping and bidi display,
  then **measure the actual shaped glyph widths** using ReportLab font
  metrics. Long words and identifiers are broken across lines if needed.
- Each column has a fixed, documented maximum number of lines:
  ID 2, title 4, status/priority/deadline 2, category/assignee 3.
  If content cannot fit, its final line ends with an explicit `…` rather
  than silently slicing the first 30 characters. A 1024-character input
  budget per cell protects the renderer from exceptionally long strings.
  CSV retains the original full text without PDF-specific clipping.
- Row height expands to fit the maximum rendered cell line count, up to
  four lines. No text is placed beyond the reserved bottom-footer zone.
- Every page shows a report heading, selected Gregorian period, all
  **seven column labels**, horizontal row dividers and its own page number.
  The first page also shows the full KPI summary. A report with zero rows
  prints an explicit empty-table message rather than a blank area.
- The exporter still consumes the **entire authorized, filtered** task
  collection passed by `dashboard_report(..., section="tasks",
  page_size=0)`, which is unchanged. PDF layout does not run SQL or
  relax the report-token/permission contract. CSV remains unchanged.

## Regression and rendering checks

`tests/test_web_report_export.py` verifies one-, multi- and empty-page
outputs, repeats of all seven headings on **each** PDF page, complete
sequence of row IDs, page footers, geometry constraints on emitted text,
word breaking based on actual glyph widths, visible truncation markers,
Persian shaping, lack-of-Unicode-font failure and unchanged CSV fidelity.
It uses a recording ReportLab canvas to validate placement, not just
the PDF magic bytes.

## Known limits

- The display PDF is an **overview**: long fields may be visibly shortened
  after the documented number of lines. Use CSV to recover complete text.
- A large report still has to load its authorized rows before PDF
  generation. The date-window guard and full-export semantics are defined
  by Issue #223; streaming an unbounded archive is out of scope.
- The new renderer embeds one Unicode font; it is not an advanced
  typography engine for every script or emoji. The supported minimum
  target is readable Persian/Arabic, English, digits and ordinary symbols.
