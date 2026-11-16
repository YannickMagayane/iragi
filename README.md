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
  <a href="https://pypi.org/project/iragi/"><img src="https://img.shields.io/pypi/v/iragi?color=green&label=PyPI" alt="PyPI Package"></a>
  <a href="#objectives"><img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg" alt="Python 3.10+"></a>
  <a href="#license"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License"></a>
  <a href="http://localhost:8000/"><img src="https://img.shields.io/badge/Docs-Sphinx-orange.svg" alt="Sphinx Docs"></a>
</p>

---

**Iragi** is a production-grade modular Python library designed for inspecting file quality, extracting unstructured document data, and running unified analysis workflows. It combines two decoupled engines — **Scan** and **PDF** — governed by an orchestration layer named **All**.

Engineered for seamless integration into standalone Python scripts, Django applications, FastAPI microservices, and data engineering pipelines, Iragi also includes a rich, modern command-line interface (CLI).

> **Core Design Principle:** Each engine functions independently. `iragi.all` coordinates the engines in a streamlined pipeline without duplicating business logic.

---

## Table of Contents

- [Objectives](#objectives)
- [Key Features](#key-features)
  - [1. iragi.scan — Tabular Quality & Profiling](#1-iragiscan--tabular-quality--profiling)
  - [2. iragi.pdf — Document Extraction](#2-iragipdf--document-extraction)
  - [3. iragi.all — Unified Orchestration](#3-iragiall--unified-orchestration)
- [Installation](#installation)
- [Quickstart (Python API)](#quickstart-python-api)
  - [Tabular Inspection with Scan](#tabular-inspection-with-scan)
  - [PDF Document Extraction](#pdf-document-extraction)
  - [End-to-End Analysis with All](#end-to-end-analysis-with-all)
- [Command Line Interface (CLI)](#command-line-interface-cli)
- [Technology Foundation & Potential](#technology-foundation--potential)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Objectives

Iragi simplifies three critical operations across modern software and data platforms:

1. **Inspect structured files** to immediately understand schema, data distributions, missing rates, and anomalies.
2. **Extract content from complex PDF documents**, including raw text, structural metadata, and embedded tabular grids.
3. **Chain extraction and quality profiling** seamlessly into an automated pipeline yielding coherent, explainable quality scores and JSON/HTML reports.

---

## Key Features

### 1. `iragi.scan` — Tabular Quality & Profiling

Inspects CSV, Excel, and JSON datasets without destructive mutations:
- **Format detection:** Auto-detection of delimiters, encodings, and spreadsheet sheets.
- **Column profiling:** Automated type inference (numeric, categorical, datetime, text), uniqueness, and cardinality metrics.
- **Completeness & Hygiene checks:** Missing value rates, null indicators, whitespace issues, and duplicate row detection.
- **Statistical anomaly detection:** Configurable Interquartile Range (IQR) and **Modified Z-Score** (median-based MAD) outlier detection — avoiding false positives on skewed or Pareto-distributed data.
- **Explainable Quality Score (0–100):** Transparent penalty breakdown across missing data, duplicates, outliers, empty columns, and critical columns (anti-dilution).
- **Data Contracts:** Declare and enforce custom business rules per column (`not_null`, `positive`, `range`, `regex` with **ReDoS timeout protection**).
- **Auto-Remediation (`auto_clean`):** Automatically cleans DataFrames (deduplication, smart numeric mean/median imputation, categorical mode imputation) without modifying original files.
- **Drift Detection (`compare_scans`):** Compares snapshots across time to highlight score degradation, schema changes, and drifting columns.
- **True Streaming (`scan_csv_stream` / `iter_csv_chunks`):** One-pass streaming inspection for multi-gigabyte CSVs with strictly bounded memory (O(chunksize)).
- **Enterprise Security:** CSV Formula Injection sanitization (`sanitize_formulas=True`) and decompression Zip Bomb defense on Excel workbooks.

### 2. `iragi.pdf` — Document Extraction

High-throughput text and table extraction from digital or scanned PDF files:
- **Fast text extraction:** Powered by PyMuPDF for lightning-fast character and page parsing.
- **Metadata parsing:** Title, author, creation dates, page counts, and security flags.
- **Table reconstruction:** Integration with `pdfplumber` to transform document tables into Pandas DataFrames.
- **Scanned page detection:** Predictive heuristic rules detecting when OCR (Tesseract / Pillow) is required.

### 3. `iragi.reconcile` — Cross-Source Data Reconciliation

Join-based reconciliation engine across heterogeneous data sources:
- **Cross-file matching:** Reconciles records between CSV, Excel, or extracted PDF tables on arbitrary keys.
- **Orphan identification:** Isolates records present in source A but missing from source B, and vice-versa.
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

---

## Quickstart (Python API)

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

## Cross-Source Data Reconciliation (`iragi.reconcile`)

Reconcile records across disparate sources (e.g. CSV vs Excel or extracted PDF tables):

```python
import iragi
import pandas as pd

df_csv = pd.read_csv("orders_crm.csv")
df_excel = pd.read_excel("invoices_erp.xlsx")

# Match on 'order_id' and cross-check 'total_amount'
result = iragi.reconcile(df_csv, df_excel, on="order_id", compare_columns=["total_amount"])

print(f"Match Rate: {result.match_rate * 100:.2f}%")
print(f"Matched records: {result.matched_count}")
print(f"Orphans in CRM only: {result.orphan_a_count}")
print(f"Orphans in ERP only: {result.orphan_b_count}")
print(f"Value conflicts on 'total_amount': {result.conflict_columns.get('total_amount', 0)}")
```

---

## Auto-Remediation & Data Cleaning (`iragi.auto_clean`)

Remediate quality defects without mutating original files:

```python
import iragi
import pandas as pd

raw_df = pd.read_csv("messy_data.csv")

clean_res = iragi.auto_clean(
    raw_df,
    drop_duplicates=True,
    impute_numeric="mean",       # or "median"
    impute_categorical="mode",
)

cleaned_df = clean_res.df
print(f"Duplicates removed: {clean_res.changes['duplicates_removed']}")
print(f"Null cells imputed: {clean_res.changes['nulls_imputed']}")
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

## True Streaming Scan for Big Data (`iragi.scan_csv_stream`)

Inspect files of any size (even 50 GB+) with strictly bounded RAM:

```python
import iragi

# Bounded memory: processes in 50,000 row chunks, never loading the whole dataset
result = iragi.scan_csv_stream("massive_dataset.csv", chunksize=50_000)

print(f"Rows: {result.row_count}, Columns: {result.column_count}")
print(f"Score: {result.quality_score.total_score:.1f}/100")
```

---

## Command Line Interface (CLI)

Iragi includes a rich CLI built with Typer and Rich:

```bash
# Check version
iragi version

# Inspect a tabular file in the terminal
iragi scan data.csv

# Export scan results to JSON
iragi scan data.xlsx --output report.json

# Extract text from PDF
iragi pdf text document.pdf

# Extract tables from PDF
iragi pdf tables document.pdf

# Run unified pipeline
iragi all report.pdf
```

---

## Technology Foundation & Potential

Iragi is built on a battle-tested Python stack:
- **High-Performance Core:** Python 3.10+, Pandas 2+, and NumPy.
- **Universal Extraction:** PyMuPDF, pdfplumber, Tesseract / Pillow.
- **Developer Experience:** Typer, Rich terminal diagnostics.
- **Reporting Engine:** Jinja2 templating for JSON and HTML reporting.
- **Industrial Rigor:** 100% automated test coverage with `pytest`, strict Sphinx API documentation.

### Ready for Strategic Integration
- **ETL & Data Warehousing:** Automated schema validation and hygiene checks before loading into Lakehouses.
- **Web Applications (Django / FastAPI):** Live validation of user-uploaded spreadsheets and PDF invoices.
- **AI & LLM RAG Pipelines:** High-fidelity data preparation, structuring documents before vector indexing.

---

## Roadmap

- [x] **Phase 1 — Foundations:** Architecture, domain models, Sphinx tooling, CI/CD.
- [x] **Phase 2 — Scan Engine:** Readers (CSV, Excel, JSON), statistical profiling, anomaly detection.
- [x] **Phase 3 — PDF Engine:** Text extraction, metadata, table reconstruction, OCR detection heuristics.
- [x] **Phase 4 — All Orchestration:** Unified pipeline, PDF-to-Scan bridge, batch processing.
- [x] **Phase 5 — Production & PyPI:** 100% test coverage, Sphinx docs, PyPI automated deployment.
- [x] **Phase 6 — Structural Hardening (v0.3.0):** Data Contracts engine, multi-sheet Excel batch, chunked CSV reading.
- [x] **Phase 7 — Enterprise Governance & Security (v0.4.0):** Cross-source reconciliation (`iragi.reconcile`), auto-remediation (`auto_clean`), drift detection (`compare_scans`), true bounded-memory streaming (`scan_csv_stream`), ReDoS protection, CSV Formula Injection defense, Zip Bomb shielding, Modified Z-score outlier detection, and anti-dilution critical columns scoring.

---

---

## 🇫🇷 Aperçu en Français

**Iragi** est une bibliothèque logicielle Python de niveau industriel dédiée à l'inspection de qualité de données et à l'extraction de documents complexes (CSV, Excel, JSON et PDF).

- **Architecture :** Deux moteurs indépendants (`iragi.scan` et `iragi.pdf`) coordonnés par un pipeline unifié (`iragi.all`).
- **Score de qualité transparent :** Note sur 100 avec explications claires des anomalies (doublons, valeurs manquantes, outliers).
- **Extraction PDF :** Récupération ultra-rapide du texte, détection de scans papier (OCR) et conversion de tableaux en DataFrames Pandas.
- **Documentation complète en français :** [Lire le guide complet en français (README.fr.md)](https://github.com/YannickMagayane/iragi/blob/main/README.fr.md).

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and submit a Pull Request.  
All PRs targeting `main` require review and approval by `@YannickMagayane`.

---

## License

This project is licensed under the [MIT License](LICENSE).
