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
- **Statistical anomaly detection:** Configurable Interquartile Range (IQR) outlier detection and date format validation.
- **Explainable Quality Score (0–100):** Transparent penalty breakdown across missing data, duplicates, and outliers.
- **Actionable recommendations:** Targeted cleanup hints generated alongside every scan.

### 2. `iragi.pdf` — Document Extraction

High-throughput text and table extraction from digital or scanned PDF files:
- **Fast text extraction:** Powered by PyMuPDF for lightning-fast character and page parsing.
- **Metadata parsing:** Title, author, creation dates, page counts, and security flags.
- **Table reconstruction:** Integration with `pdfplumber` to transform document tables into Pandas DataFrames.
- **Scanned page detection:** Predictive heuristic rules detecting when OCR (Tesseract / Pillow) is required.

### 3. `iragi.all` — Unified Orchestration

A single interface to rule them all:
- **Universal entrypoint:** `iragi.analyze(file_path)` determines file type and runs the optimal pipeline.
- **PDF-to-Scan bridge:** Automatically extracts tables from PDF files and feeds them straight into the quality scan profiler.
- **Batch processing:** Analyze entire directories or file collections simultaneously with `iragi.batch_analyze([...])`.

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

print(f"Type: {result.file_type}, Score: {result.quality_score.total_score if result.quality_score else 'N/A'}")
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
