# Iragi

<p align="center">
  <strong>🇬🇧 English</strong> &nbsp;|&nbsp; <a href="https://github.com/YannickMagayane/iragi/blob/main/README.fr.md">🇫🇷 Lire en Français</a>
</p>

<p align="center">
  <strong>Inspect. Extract. Analyze.</strong><br>
  <em>Modular Python toolkit for high-performance data quality inspection and document extraction.</em>
</p>

<p align="center">
  <a href="https://github.com/YannickMagayane/iragi"><img src="https://img.shields.io/badge/GitHub-YannickMagayane%2Firagi-181717?style=flat&logo=github&logoColor=white" alt="GitHub Repository"></a>
  <a href="https://pypi.org/project/iragi/"><img src="https://img.shields.io/pypi/v/iragi" alt="PyPI"></a>
  <a href="https://pypi.org/project/iragi/"><img src="https://img.shields.io/pypi/pyversions/iragi" alt="Python"></a>
  <a href="https://github.com/YannickMagayane/iragi/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/iragi" alt="License"></a>
  <a href="https://pepy.tech/project/iragi"><img src="https://static.pepy.tech/badge/iragi/month" alt="Downloads"></a>
  <a href="https://github.com/YannickMagayane/iragi/actions"><img src="https://img.shields.io/github/actions/workflow/status/YannickMagayane/iragi/ci.yml" alt="CI"></a>
  <a href="https://codecov.io/gh/YannickMagayane/iragi"><img src="https://codecov.io/gh/YannickMagayane/iragi/branch/main/graph/badge.svg" alt="codecov"></a>
  <a href="https://github.com/YannickMagayane/iragi/tree/main/docs/source"><img src="https://img.shields.io/badge/Docs-Sphinx-orange.svg" alt="Sphinx Docs"></a>
</p>

---

**Iragi** is a modular Python library for inspecting file quality, extracting unstructured document data, and running unified analysis workflows. It combines two decoupled engines — **Scan** and **PDF** — governed by an orchestration layer named **All**.

Engineered for seamless integration into standalone Python scripts, Django applications, FastAPI microservices, and data engineering pipelines, Iragi also includes a rich, modern command-line interface (CLI).

> **Core Design Principle:** Each engine functions independently. `iragi.all` coordinates the engines in a streamlined pipeline without duplicating business logic.

---

## Table of Contents

- [Objectives](#objectives)
- [Key Features](#key-features)
  - [1. iragi.scan — Tabular Quality & Profiling](#1-iragiscan--tabular-quality--profiling)
  - [2. iragi.pdf — Document Extraction & Streaming](#2-iragipdf--document-extraction--streaming)
  - [3. iragi.reconcile — Cross-Source Data Reconciliation](#3-iragireconcile--cross-source-data-reconciliation)
  - [4. iragi.all — Unified Orchestration](#4-iragiall--unified-orchestration)
- [Installation](#installation)
- [Quickstart (Python API)](#quickstart-python-api)
  - [Tabular Inspection with Scan](#tabular-inspection-with-scan)
  - [PDF Document Extraction](#pdf-document-extraction)
  - [End-to-End Analysis with All](#end-to-end-analysis-with-all)
- [Data Contracts — Custom Business Rules](#data-contracts--custom-business-rules)
- [Multi-Sheet Excel Batch Audit](#multi-sheet-excel-batch-audit)
- [Large File Support (Chunked Reading)](#large-file-support-chunked-reading)
- [Deterministic Auto-Remediation & Dead-Letter Quarantine](#deterministic-auto-remediation--dead-letter-quarantine-iragiauto_clean)
- [Cross-Source Reconciliation & Regex Normalization](#cross-source-reconciliation--regex-normalization-iragireconcile)
- [Multi-Source Consensus Reconciliation](#multi-source-consensus-reconciliation-iragireconcile_multi)
- [Chunked Processing for Large Files (CSV, Excel, PDF)](#chunked-processing-for-large-files-csv-excel-pdf)
- [Data Drift Detection](#data-drift-detection-iragicompare_scans)
- [Command Line Interface (CLI)](#command-line-interface-cli)
- [Technology Foundation & Potential](#technology-foundation--potential)
- [Benchmarks](#benchmarks)
- [Changelog](#changelog)
- [Contributing](#contributing)
- [License](#license)

---

## Objectives

Iragi simplifies critical operations across modern software and data platforms:

1. **Inspect structured files** (CSV, Excel, JSON, Parquet) to immediately understand schema, data distributions, missing rates, and anomalies.
2. **Extract content from complex PDF documents**, including raw text, structural metadata, and embedded tabular grids.
3. **Cross-source reconciliation** between disparate datasets with regex-based key normalization and consensus tracking.
4. **Deterministic remediation and dead-letter quarantine (DLQ)** without altering source files or blindly imputing financial equations.
5. **Chain extraction, quality profiling, and chunked processing** into an automated pipeline with configurable working-set limits.

---

## Key Features

### 1. `iragi.scan` — Tabular Quality & Profiling

Inspects CSV, Excel (.xlsx, .xls), JSON, and Apache Parquet (.parquet, .pq) datasets without destructive mutations:
- **Format detection:** Auto-detection of delimiters, encodings, and spreadsheet sheets.
- **Column profiling:** Automated type inference (numeric, categorical, datetime, text), uniqueness, and cardinality metrics.
- **Completeness & Hygiene checks:** Missing value rates, null indicators, whitespace issues, and duplicate row detection.
- **Statistical anomaly detection:** Configurable Interquartile Range (IQR) and **Modified Z-Score** (median-based MAD) outlier detection — avoiding false positives on skewed or Pareto-distributed data.
- **Explainable Quality Score (0–100):** Transparent penalty breakdown across missing data, duplicates, outliers, empty columns, critical column anti-dilution, and customizable `column_weights`.
- **Data Contracts:** Declare and enforce custom business rules per column (`not_null`, `positive`, `range`, `regex` with cross-platform **ReDoS timeout protection**).
- **Deterministic Auto-Remediation (`auto_clean`):** Applies deduplication, fuzzy string deduplication (`fuzzy_dedup=True`), formula-based deterministic calculations (`computed_columns`), per-column imputation strategies (`impute_strategies`), and sensitive column exclusion (`exclude_columns`).
- **Dead-Letter Queue Quarantine (DLQ):** When coupled with a `DataContract`, `auto_clean` isolates violating records into a dedicated `quarantine_df` while returning cleaned data in `df`.
- **Chunked processing (`scan_csv_stream`, `scan_excel_stream`, `scan_jsonl_stream`):** Process CSV, Excel and JSON Lines inputs in chunks. Duplicate detection retains row hashes proportional to distinct rows, and streaming scores are estimates based on sampled statistics.
- **Input safeguards:** Optional CSV formula sanitization, hardened XML parsing, and archive size and compression-ratio limits for spreadsheet files.

### 2. `iragi.pdf` — Document Extraction & Streaming

High-throughput text and table extraction from digital or scanned PDF files:
- **Fast text extraction:** Powered by PyMuPDF for lightning-fast character and page parsing.
- **Metadata parsing:** Title, author, creation dates, page counts, and security flags.
- **Table reconstruction:** Integration with `pdfplumber` to transform document tables into Pandas DataFrames.
- **Scanned page detection:** Predictive heuristic rules detecting when OCR (Tesseract / Pillow) is required.
- **Memory-bounded PDF Streaming (`iter_pdf_pages`, `extract_tables_stream`):** Page-by-page generator processing preventing memory exhaustion on 1,000+ page documents.

### 3. `iragi.reconcile` — Cross-Source Data Reconciliation

Join-based reconciliation engine across heterogeneous data sources:
- **Heterogeneous key matching:** Reconcile across different column names via tuple syntax `on=("order_id", "facture_id")`.
- **Key Normalization & Regex (`key_transform`):** Cleanly strip varying prefixes (e.g. `TRX-101` vs `FACT_101`) using regex patterns like `r"(\d+)"` or custom callables.
- **Consensus Multi-Reconciliation (`reconcile_multi`):** Reconcile 3 or more datasets simultaneously, computing shared consensus keys and source-specific orphan counts.
- **Value conflict detection:** Identifies field-by-field discrepancies between matched records.
- **Match Rate:** Computes definitive reconciliation coverage percentage.

### 4. `iragi.all` — Unified Orchestration

A single interface to rule them all:
- **Universal entrypoint:** `iragi.analyze(file_path)` determines file type and runs the optimal pipeline.
- **PDF-to-Scan bridge:** Automatically extracts tables from PDF files and feeds them straight into the quality scan profiler.
- **Batch processing:** Analyze entire directories or file collections simultaneously with `iragi.batch_analyze([...])`.
- **Multi-sheet Excel batch:** Pass `excel_all_sheets=True` to audit every sheet of every workbook independently.

---

## Installation

```bash
# Core installation (tabular scan, CLI, reporting)
pip install iragi

# With PDF extraction support
pip install "iragi[pdf]"

# With OCR support
pip install "iragi[ocr]"

# Full installation (all engines, OCR, docs)
pip install "iragi[all]"
```

The `pdf` extra installs [PyMuPDF](https://github.com/pymupdf/PyMuPDF), offered under AGPL-3.0 or a separate commercial license. Review its [licensing terms](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright) before distribution.

---

## Quickstart (Python API)

For a ready-to-run notebook, open [examples/quickstart.ipynb](https://github.com/YannickMagayane/iragi/blob/main/examples/quickstart.ipynb).

### Tabular Inspection with Scan

```python
import iragi.scan as scan

# Inspect any CSV, Excel or JSON file
result = scan.scan("sales_2026.csv")

print(f"Rows: {result.row_count}, Columns: {result.column_count}")
print(f"Overall Quality Score: {result.quality_score.total_score:.1f}/100")

# Access column profiles
for col in result.column_profiles:
    print(f"Column '{col.name}': {col.inferred_type} ({col.missing_percentage:.1f}% missing)")
```

### PDF Document Extraction

```python
import iragi.pdf as pdf

# Extract complete document structure
doc = pdf.extract("contract.pdf")

print(f"Pages: {doc.page_count}, Scanned: {doc.is_scanned}")
for table in doc.tables:
    df = table.to_dataframe()
    print(df.head())
```

### End-to-End Analysis with All

```python
import iragi

# Automatically routes to Scan or PDF engine
result = iragi.analyze("quarterly_report.pdf")

print(f"Type: {result.file_type}, Score: {result.overall_quality_score:.1f}/100")
```

---

## Data Contracts — Custom Business Rules

Declare and enforce column-level rules on any DataFrame:

```python
import iragi
import pandas as pd

df = pd.read_csv("invoices.csv")

contract = (
    iragi.DataContract()
    .require_not_null("invoice_id")                      # no null values allowed
    .require_positive("amount")                          # amount must be > 0
    .require_range("tax_rate", min_val=0, max_val=100)   # percentage 0–100
    .require_regex("email", r"^[^@]+@[^@]+\.[^@]+$")    # valid email format
)

violations = iragi.validate_contract(df, contract)

if violations:
    for v in violations:
        print(f"[{v.rule}] Column '{v.column}': {v.detail}")
else:
    print("All business rules passed.")
```

---

## Multi-Sheet Excel Batch Audit

```python
import iragi

# Audit every sheet of every Excel workbook independently
results = iragi.batch_analyze(["annual_report.xlsx"], excel_all_sheets=True)

for r in results:
    status = "OK" if r.success else "FAILED"
    print(f"{r.file_path} → {r.overall_quality_score:.1f}/100 [{status}]")
```

---

## Large File Support (Chunked Reading)

```python
from iragi.scan import read_csv_chunked

# Process a large CSV without memory overflow
df = read_csv_chunked("transactions_2026.csv", chunksize=100_000)

print(f"Total rows loaded: {len(df)}")
print(f"Detected delimiter: {df.attrs.get('delimiter')}")
```

---

## Deterministic Auto-Remediation & Dead-Letter Quarantine (`iragi.auto_clean`)

Standard statistical imputation (e.g. blind mean) can corrupt business logic like `net_amount = (unit_price * qty) * (1 - discount) + shipping`. Iragi provides **deterministic formula rules**, **sensitive column exemptions**, and **dead-letter queue (DLQ) quarantine** for contract violations:

```python
import iragi
import pandas as pd

raw_df = pd.read_csv("transactions.csv")

# 1. Enforce business contract rules
contract = (
    iragi.DataContract()
    .require_positive("net_amount")
    .require_regex("status", r"^(PAID|FAILED)$")
)

# 2. Remediation with business formulas & dead-letter queue
clean_res = iragi.auto_clean(
    raw_df,
    drop_duplicates=True,
    fuzzy_dedup=True,
    fuzzy_columns=["customer_name"],
    # Deterministic equation replaces blind statistical guessing
    computed_columns={
        "net_amount": lambda d: (d["unit_price"] * d["qty"]) * (1.0 - d["discount"]) + d["shipping"]
    },
    exclude_columns=["sensitive_id"],
    contract=contract,
    contract_action="quarantine",  # isolates corrupt rows in DLQ instead of corrupting data
)

clean_df = clean_res.df
dlq_df = clean_res.quarantine_df

print(f"Clean records ready for analytics: {len(clean_df)}")
print(f"Corrupt records quarantined in DLQ: {len(dlq_df)}")
print(f"Duplicates removed: {clean_res.changes.get('duplicates_removed', 0)}")
print(f"Fuzzy duplicates removed: {clean_res.changes.get('fuzzy_duplicates_removed', 0)}")
```

---

## Cross-Source Reconciliation & Regex Normalization (`iragi.reconcile`)

Reconcile records across disparate sources even when systems use different column names or sequence prefixes (e.g. Sales uses `TRX-101`, Finance uses `FACT_101`):

```python
import iragi
import pandas as pd

df_sales = pd.read_csv("sales.csv")          # column: order_id ('TRX-101')
df_finance = pd.read_excel("finance.xlsx")   # column: invoice_id ('FACT_101')

# Match with regex normalization to extract core sequence numbers
result = iragi.reconcile(
    df_sales,
    df_finance,
    on=("order_id", "invoice_id"),
    key_transform=r"(\d+)",
    compare_columns=["amount"],
)

print(f"Match Rate: {result.match_rate * 100:.2f}%")
print(f"Matched records: {result.matched_count}")
print(f"Orphans in Sales only: {result.orphan_a_count}")
print(f"Orphans in Finance only: {result.orphan_b_count}")
print(f"Amount conflicts: {result.conflict_columns.get('amount', 0)}")
```

---

## Multi-Source Consensus Reconciliation (`iragi.reconcile_multi`)

Audit consensus across 3 or more systems (e.g. Sales vs Logistics vs Accounting):

```python
import iragi

res = iragi.reconcile_multi(
    {"sales": df_sales, "logistics": df_logistics, "finance": df_finance},
    on="reference_id",
    key_transform=lambda k: "".join(filter(str.isdigit, str(k))),
)

print(f"Consensus matched across all 3 systems: {res.all_matched_count}")
print(f"Total unique keys: {res.total_unique_keys}")
print(f"Consensus match rate: {res.consensus_match_rate * 100:.2f}%")
print(f"Orphans by source: {res.orphans_by_source}")
```

---

## Chunked Processing for Large Files (CSV, Excel, PDF)

CSV, Excel and JSON Lines readers can process input in chunks. Streaming scans retain duplicate row hashes proportional to distinct rows, and calculate statistical scores from samples; their scores are marked as estimates. PDF page and table iterators yield results as they are read.

```python
import iragi
from iragi.scan import scan_csv_stream, scan_excel_stream, iter_excel_chunks
from iragi.pdf import iter_pdf_pages, extract_tables_stream

# 1. Stream massive CSV (50 GB+) in 50,000 row chunks
res_csv = scan_csv_stream("large_data.csv", chunksize=50_000)
print(f"CSV score: {res_csv.quality_score.total_score:.1f}/100")

# 2. Stream massive multi-sheet Excel (300 MB+) without memory spikes
res_excel = scan_excel_stream("large_workbook.xlsx", sheet_name="01_Ventes", chunksize=25_000)
print(f"Excel score: {res_excel.quality_score.total_score:.1f}/100")

# 3. Stream multi-thousand page PDF page-by-page
for page in iter_pdf_pages("huge_report.pdf", batch_size=10):
    if page.is_scanned:
        print(f"Page {page.page_number} requires OCR")

# 4. Stream tables from PDF on the fly
for table in extract_tables_stream("huge_report.pdf"):
    df_chunk = table.to_dataframe()
    # Process or load table to warehouse immediately
```

---

## Data Drift Detection (`iragi.compare_scans`)

Monitor data distributions across time or pipeline runs:

```python
import iragi

scan_yesterday = iragi.scan("data_2026_01_01.csv")
scan_today = iragi.scan("data_2026_01_02.csv")

drift = iragi.compare_scans(scan_yesterday, scan_today)

print(f"Quality delta: {drift.score_delta:+.2f} pts")
print(f"Missing count delta: {drift.missing_delta:+d}")
print(f"Drifted columns: {drift.drifted_columns}")
print(f"Summary: {drift.summary}")
```

---

## Command Line Interface (CLI)

Iragi includes a rich CLI built with Typer and Rich:

```bash
# Check version
iragi version

# Inspect a local file
iragi scan data.csv

# Inspect a remote file directly from a URL
iragi scan https://data.gov/resources/air_quality_annual.csv

# Export scan results to JSON
iragi scan data.xlsx --output report.json

# Extract text from PDF
iragi pdf text document.pdf

# Extract tables from PDF
iragi pdf tables document.pdf

# Run unified pipeline on a remote file
iragi all https://www.insee.fr/en/statistiques/fichier/emploi_2026.xlsx
```

---

## Remote and Cloud File Ingestion

Iragi accepts HTTP or HTTPS URLs wherever a local file path is expected. Remote requests reject private and non-routable IP addresses, follow at most five validated redirects, and can be restricted with `allowed_hosts`.
No configuration is needed. Files are fetched transparently, inspected in memory, and the
temporary copy is deleted automatically.

### Supported sources

- **Open Data portals:** data.gov, data.world, Kaggle, INSEE, WHO, Eurostat
- **Cloud storage:** AWS S3 presigned URLs, Google Cloud Storage, Azure Blob Storage
- **Any direct download link:** research datasets, financial reports, sensor telemetry

### Examples

```python
import iragi

# Inspect a CSV directly from an open data portal
result = iragi.scan("https://data.gov/resources/air_quality_annual.csv")
print(f"Rows: {result.row_count}, Score: {result.quality_score.total_score}/100")

# Inspect a Parquet file from Google Cloud Storage
result = iragi.scan("https://storage.googleapis.com/climate/co2_monitoring.parquet")
print(f"Columns: {result.columns}")

# Full unified analysis on a remote Excel government report
res = iragi.analyze("https://www.insee.fr/en/statistiques/fichier/emploi_2026.xlsx")
print(f"File type: {res.file_type}, Score: {res.overall_quality_score}/100")

# Batch-analyze a mix of local and remote files (any file type, any domain)
results = iragi.batch_analyze([
    "local_data/internal_sales.csv",
    "https://opendata.health.org/clinical_trials.parquet",
    "https://s3.amazonaws.com/mybucket/logistics/shipments.xlsx",
    "https://ftp.gov.org/archive/population_2026.json",
])
for r in results:
    print(f"{r.file_path}: {r.overall_quality_score}/100")
```

### Safety guarantees

| Protection | Default value |
|---|---|
| Maximum file size | 500 MB |
| Network timeout | 30 seconds |
| Temporary file cleanup | Automatic (always) |

> **Note:** S3 and GCS private buckets require presigned URLs. Iragi fetches any HTTPS URL,
> so presigned URLs work out of the box without additional configuration or AWS/GCP credentials.

---

## Technology Foundation & Potential

Iragi uses a Python stack that includes:
- **High-Performance Core:** Python 3.10+, Pandas 2+, and NumPy.
- **Universal Extraction:** PyMuPDF, pdfplumber, Tesseract / Pillow.
- **Developer Experience:** Typer, Rich terminal diagnostics.
- **Reporting Engine:** Jinja2 templating for JSON and HTML reporting.
- **Quality Checks:** GitHub Actions tests Python 3.10–3.13 on Linux and Windows with pandas 2.x/3.x; coverage is uploaded to Codecov.

### Ready for Strategic Integration
- **ETL & Data Warehousing:** Automated schema validation and hygiene checks before loading into Lakehouses.
- **Web Applications (Django / FastAPI):** Live validation of user-uploaded spreadsheets and PDF invoices.
- **AI & LLM RAG Pipelines:** High-fidelity data preparation, structuring documents before vector indexing.

---

## Benchmarks

Re-run the CSV and PDF timing suite with `python bench_suite.py --rows 100000 --output benchmarks/results.json`. The checked-in [results](https://github.com/YannickMagayane/iragi/blob/main/benchmarks/results.json) are a local Python 3.14.4/Linux sample. Reported memory is Python-traced allocation and excludes pandas/NumPy native allocations; timings are hardware-dependent.

## Changelog

See [CHANGELOG.md](https://github.com/YannickMagayane/iragi/blob/main/CHANGELOG.md) for release notes.

---

## 🇫🇷 Aperçu en Français

**Iragi** est une bibliothèque logicielle Python de niveau industriel dédiée à l'inspection de qualité de données et à l'extraction de documents complexes (CSV, Excel, JSON et PDF).

- **Architecture :** Deux moteurs indépendants (`iragi.scan` et `iragi.pdf`) coordonnés par un pipeline unifié (`iragi.all`).
- **Score de qualité transparent :** Note sur 100 avec explications claires des anomalies (doublons, valeurs manquantes, outliers).
- **Extraction PDF :** Récupération ultra-rapide du texte, détection de scans papier (OCR) et conversion de tableaux en DataFrames Pandas.
- **Documentation complète en français :** [Lire le guide complet en français (README.fr.md)](https://github.com/YannickMagayane/iragi/blob/main/README.fr.md).

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](https://github.com/YannickMagayane/iragi/blob/main/CONTRIBUTING.md) and submit a Pull Request.
All PRs targeting `main` require review and approval by `@YannickMagayane`.

---

## License

This project is licensed under the [MIT License](https://github.com/YannickMagayane/iragi/blob/main/LICENSE).
