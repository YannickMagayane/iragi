# Changelog

## 0.6.4 — Benchmark and workflow update (2026-11-17)

- Expand the reproducible benchmark to cover CSV, JSON Lines, Excel and PDF workloads, contract validation, auto-clean with DLQ quarantine, and two-source reconciliation.
- Add English and French feature-matrix graphics comparing Iragi with Great Expectations, Pandera, ydata-profiling and Soda Core.
- Close pandas Excel workbooks after reads so temporary workbooks can be removed on Windows.
- Skip Codecov upload when `CODECOV_TOKEN` is not configured, while keeping test execution independent of that optional secret.

## 0.6.3 — Release candidate (2026-11-17)

- Make `iragi.scan` callable as a module so `import iragi.scan.engine as engine` works.
- Keep Pillow optional and lazy-load it only for OCR operations.
- Count non-numeric, non-null values as violations in positive and range contracts.
- Stream XML member parsing through `defusedxml`; check archive expansion limits before parsing members.
- Remove partial remote downloads after failures and block non-public destinations, with redirect validation and optional host allowlists across scan, analyze and batch APIs.
- Probe CSV encoding and delimiter from at most 1,000 lines and parse once with pandas' C engine.
- Count cross-chunk CSV, Excel and JSON Lines duplicates using row hashes; mark streaming scores as estimates.
- Add chunked JSON Lines scanning and formula sanitization for Excel reads and `auto_clean` output.
- Expand CI across Python 3.10–3.13, pandas 2.x/3.x, Linux and Windows; publish coverage and audit dependencies.

