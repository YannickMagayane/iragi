#!/usr/bin/env python3
"""Benchmark Iragi profiling, rules, cleaning, reconciliation, PDF and streaming.

Run ``python bench_suite.py --rows 100000 --repeat 5``. The command writes
``benchmarks/results.json``, ``benchmarks/benchmark.svg`` and capability charts.

Each timed sample runs in a fresh process after one unmeasured warm-up for that
mode. Timings exclude imports. The memory metric is Python-traced allocation;
native allocations in pandas, NumPy and PyMuPDF are not included. Results are
descriptive measurements for the recorded machine, not performance guarantees.
"""

from __future__ import annotations

import argparse
import hashlib
import html
from importlib import metadata
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any

import pandas as pd


_FRAMEWORKS = (
    {
        "name": "Iragi",
        "distribution": "iragi",
        "focus": "File inspection, profiling, quality scoring",
        "scope": "Runtime and Python-traced allocation recorded for each included workload",
    },
    {
        "name": "Great Expectations",
        "distribution": "great_expectations",
        "focus": "Expectation-based data validation",
        "scope": "Validation; setup and suites are configurable",
    },
    {
        "name": "Pandera",
        "distribution": "pandera",
        "focus": "Pandas DataFrame schema validation",
        "scope": "Schema and custom checks on in-memory frames",
    },
    {
        "name": "ydata-profiling",
        "distribution": "ydata-profiling",
        "focus": "Descriptive profiling and HTML reports",
        "scope": "Statistical profiling; broader work than validation",
    },
    {
        "name": "Soda Core",
        "distribution": "soda-core",
        "focus": "SodaCL checks for data sources",
        "scope": "Pandas adapter and Soda Cloud configuration needed for DataFrames",
    },
)

_CAPABILITIES = (
    {
        "name": "Profiling",
        "values": {"Iragi": "Yes", "Great Expectations": "Partial", "Pandera": "No", "ydata-profiling": "Yes", "Soda Core": "Partial"},
    },
    {
        "name": "Contracts / rules",
        "values": {"Iragi": "Yes", "Great Expectations": "Yes", "Pandera": "Yes", "ydata-profiling": "Partial", "Soda Core": "Yes"},
    },
    {
        "name": "PDF extraction",
        "values": {"Iragi": "Yes", "Great Expectations": "No", "Pandera": "No", "ydata-profiling": "No", "Soda Core": "No"},
    },
    {
        "name": "Reconciliation",
        "values": {"Iragi": "Yes", "Great Expectations": "Partial", "Pandera": "Partial", "ydata-profiling": "No", "Soda Core": "Partial"},
    },
    {
        "name": "Auto-clean + DLQ",
        "values": {"Iragi": "Yes", "Great Expectations": "No", "Pandera": "No", "ydata-profiling": "No", "Soda Core": "No"},
    },
    {
        "name": "Large-file streaming",
        "values": {"Iragi": "Yes", "Great Expectations": "Partial", "Pandera": "Partial", "ydata-profiling": "Partial", "Soda Core": "Partial"},
    },
)


def _framework_inventory() -> list[dict[str, Any]]:
    """Describe optional competitor packages without implying unrun timings."""
    inventory = []
    for framework in _FRAMEWORKS:
        if framework["name"] == "Iragi":
            from iragi import __version__ as version
            installed = True
        else:
            try:
                version = metadata.version(framework["distribution"])
                installed = True
            except metadata.PackageNotFoundError:
                version = None
                installed = False
        inventory.append({**framework, "installed": installed, "version": version})
    soda_credentials = bool(
        os.environ.get("SODA_CLOUD_API_KEY_ID")
        and os.environ.get("SODA_CLOUD_API_KEY_SECRET")
    )
    for framework in inventory:
        if framework["name"] == "Iragi":
            framework["timed"] = True
            framework["status"] = "benchmarked across the workloads in this report"
        elif framework["name"] == "Soda Core":
            framework["pandas_adapter_installed"] = metadata.version("soda-pandas-dask") if _has_distribution("soda-pandas-dask") else None
            framework["cloud_credentials_configured"] = soda_credentials
            framework["timed"] = False
            framework["status"] = "needs optional adapter and Soda Cloud credentials for in-memory DataFrame scans"
        else:
            framework["timed"] = False
            framework["status"] = "not timed; optional package is not installed" if not framework["installed"] else "installed; not timed by this suite"
    return inventory


def _has_distribution(name: str) -> bool:
    """Return whether an optional distribution is installed."""
    try:
        metadata.version(name)
        return True
    except metadata.PackageNotFoundError:
        return False


def _normalized_digest(text: str) -> tuple[str, int]:
    """Return a whitespace-normalized text digest and its normalized length."""
    normalized = " ".join(text.split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return digest, len(normalized)


def _child(mode: str, input_path: Path, chunksize: int, other_path: Path | None = None) -> dict[str, Any]:
    """Run a workload; library imports and shared input loading are excluded."""
    import iragi

    dataframe = None
    other_dataframe = None
    if mode in {"contract", "auto_clean_dlq", "reconcile"}:
        dataframe = pd.read_csv(input_path)
        if mode == "reconcile":
            if other_path is None:
                raise ValueError("reconcile mode requires --other-input")
            other_dataframe = pd.read_csv(other_path)
    if mode in {"contract", "auto_clean_dlq"}:
        from iragi.scan.contract import DataContract
    if mode == "contract":
        from iragi.scan.contract import validate_contract
    if mode == "auto_clean_dlq":
        from iragi.scan.cleaner import auto_clean
    if mode == "reconcile":
        from iragi.reconcile.engine import reconcile
    if mode == "excel_stream":
        from iragi.scan.engine import scan_excel_stream
    if mode == "jsonl_stream":
        from iragi.scan.engine import scan_jsonl_stream
    if mode == "pdf_pages":
        from iragi.pdf.extractor import iter_pdf_pages
    if mode == "pdf_pymupdf":
        import pymupdf
    if mode == "pdf_iragi":
        from iragi.pdf import extract
    tracemalloc.start()
    tracemalloc.reset_peak()
    started = time.perf_counter()

    if mode == "pandas":
        result = pd.read_csv(input_path)
        summary = {"rows": len(result), "columns": len(result.columns)}
    elif mode == "classic":
        result = iragi.scan(input_path)
        summary = {
            "rows": result.row_count,
            "score": result.quality_score.total_score,
            "duplicate_rows": result.duplicate_rows_count,
        }
    elif mode == "stream":
        result = iragi.scan(input_path, stream=True, chunksize=chunksize)
        summary = {
            "rows": result.row_count,
            "score": result.quality_score.total_score,
            "duplicate_rows": result.duplicate_rows_count,
            "score_is_estimated": result.score_is_estimated,
        }
    elif mode == "jsonl_pandas":
        result = pd.read_json(input_path, lines=True)
        summary = {"rows": len(result), "columns": len(result.columns)}
    elif mode == "jsonl_stream":
        result = scan_jsonl_stream(input_path, chunksize=chunksize)
        summary = {
            "rows": result.row_count,
            "duplicate_rows": result.duplicate_rows_count,
            "score": result.quality_score.total_score,
            "score_is_estimated": result.score_is_estimated,
        }
    elif mode == "excel_classic":
        result = iragi.scan(input_path)
        summary = {
            "rows": result.row_count,
            "score": result.quality_score.total_score,
            "duplicate_rows": result.duplicate_rows_count,
        }
    elif mode == "excel_stream":
        result = scan_excel_stream(input_path, chunksize=chunksize)
        summary = {
            "rows": result.row_count,
            "score": result.quality_score.total_score,
            "duplicate_rows": result.duplicate_rows_count,
            "score_is_estimated": result.score_is_estimated,
        }
    elif mode == "contract":
        contract = DataContract().require_positive("amount").require_range("amount", 1, 10_000)
        violations = validate_contract(dataframe, contract)
        rule_failure_counts = {violation.rule: violation.failed_count for violation in violations}
        summary = {
            "rows": len(dataframe),
            "rules": 2,
            "rule_failure_counts": rule_failure_counts,
        }
    elif mode == "auto_clean_dlq":
        contract = DataContract().require_positive("amount")
        result = auto_clean(dataframe, contract=contract, contract_action="quarantine")
        summary = {
            "input_rows": len(dataframe),
            "clean_rows": len(result.df),
            "quarantined_rows": len(result.quarantine_df),
            "duplicates_removed": result.changes.get("duplicates_removed", 0),
            "contract_rule_violations": len(result.contract_violations),
        }
    elif mode == "reconcile":
        result = reconcile(
            dataframe, other_dataframe, on="record_id", compare_columns=["amount"]
        )
        summary = {
            "source_a_rows": len(dataframe),
            "source_b_rows": len(other_dataframe),
            "matched": result.matched_count,
            "orphans_a": result.orphan_a_count,
            "orphans_b": result.orphan_b_count,
            "conflict_counts": result.conflict_columns,
        }
    elif mode == "pdf_pymupdf":
        with pymupdf.open(input_path) as document:
            page_count = len(document)
            text = "\n".join(page.get_text() for page in document)
        digest, characters = _normalized_digest(text)
        summary = {
            "pages": page_count, "characters": characters, "text_sha256": digest,
            "page_markers": text.count("Iragi benchmark page"),
        }
    elif mode == "pdf_iragi":
        result = extract(input_path, extract_tables=False)
        digest, characters = _normalized_digest(result.full_text)
        summary = {
            "pages": result.page_count, "characters": characters, "text_sha256": digest,
            "page_markers": result.full_text.count("Iragi benchmark page"),
        }
    elif mode == "pdf_pages":
        page_count = 0
        character_count = 0
        marker_count = 0
        digest = hashlib.sha256()
        first_token = True
        for page in iter_pdf_pages(input_path):
            page_count += 1
            marker_count += page.text.count("Iragi benchmark page")
            for token in page.text.split():
                if not first_token:
                    digest.update(b" ")
                digest.update(token.encode("utf-8"))
                character_count += len(token) + (0 if first_token else 1)
                first_token = False
        summary = {
            "pages": page_count,
            "characters": character_count,
            "text_sha256": digest.hexdigest(),
            "page_markers": marker_count,
        }
    else:
        raise ValueError(f"Unsupported benchmark mode: {mode}")

    seconds = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"seconds": seconds, "python_traced_peak_bytes": peak, **summary}


def _run_child(mode: str, input_path: Path, chunksize: int, other_path: Path | None = None) -> dict[str, Any]:
    """Execute one isolated benchmark sample and decode its JSON result."""
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--child",
        mode,
        "--input",
        str(input_path),
        "--chunksize",
        str(chunksize),
    ]
    if other_path:
        command.extend(["--other-input", str(other_path)])
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def _summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Report median, range, raw samples, and result fields for one mode."""
    seconds = [sample["seconds"] for sample in samples]
    traced = [sample["python_traced_peak_bytes"] for sample in samples]
    summary = {
        "median_seconds": statistics.median(seconds),
        "min_seconds": min(seconds),
        "max_seconds": max(seconds),
        "median_python_traced_peak_bytes": statistics.median(traced),
        "samples": samples,
    }
    summary.update({key: value for key, value in samples[-1].items() if key not in summary})
    return summary


def _ground_truth_report(results: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    """Score exact output checks against the synthetic fixture's known answers.

    This measures whether the measured operations return seeded counts and
    cross-engine text matches. It is not a measure of general data-quality
    accuracy, anomaly recall on real data, or the quality score's validity.
    """
    workload_checks: dict[str, list[dict[str, Any]]] = {}

    def check(workload: str, label: str, observed: Any, expected: Any) -> None:
        workload_checks.setdefault(workload, []).append({
            "check": label,
            "expected": expected,
            "observed": observed,
            "passed": observed == expected,
        })

    rows = fixture["csv_rows"]
    duplicate_rows = fixture["csv_expected_duplicate_rows"]
    unique_rows = rows - duplicate_rows
    expected_zero_rows = (unique_rows + 9_999) // 10_000 + (duplicate_rows + 9_999) // 10_000
    expected_zero_after_dedup = (unique_rows + 9_999) // 10_000

    csv = results["csv"]
    for key, label in (("iragi_classic", "classic"), ("iragi_stream", "stream")):
        check(f"CSV {label}", "row count", csv[key]["rows"], rows)
        check(f"CSV {label}", "duplicate rows", csv[key]["duplicate_rows"], duplicate_rows)
    check("CSV parser", "row count", csv["pandas_read_csv"]["rows"], rows)

    jsonl = results["jsonl"]
    check("JSONL parser", "row count", jsonl["pandas_read_jsonl"]["rows"], fixture["jsonl_rows"])
    check("JSONL stream", "row count", jsonl["iragi_jsonl_stream"]["rows"], fixture["jsonl_rows"])
    check("JSONL stream", "duplicate rows", jsonl["iragi_jsonl_stream"]["duplicate_rows"], duplicate_rows)

    excel = results["excel"]
    excel_rows = fixture["excel_rows"]
    excel_duplicates = excel_rows - (excel_rows - excel_rows // 10)
    for key, label in (("iragi_excel_classic", "classic"), ("iragi_excel_stream", "stream")):
        check(f"Excel {label}", "row count", excel[key]["rows"], excel_rows)
        check(f"Excel {label}", "duplicate rows", excel[key]["duplicate_rows"], excel_duplicates)

    operations = results["operations"]
    contract_counts = operations["iragi_contract_validation"]["rule_failure_counts"]
    check("Contract validation", "positive-rule failed rows", contract_counts.get("positive", 0), expected_zero_rows)
    check("Contract validation", "range-rule failed rows", contract_counts.get("range", 0), expected_zero_rows)
    cleaning = operations["iragi_auto_clean_dlq"]
    check("Auto-clean + DLQ", "duplicates removed", cleaning["duplicates_removed"], duplicate_rows)
    check("Auto-clean + DLQ", "quarantined invalid rows", cleaning["quarantined_rows"], expected_zero_after_dedup)
    check("Auto-clean + DLQ", "clean row count", cleaning["clean_rows"], unique_rows - expected_zero_after_dedup)

    reconciliation = operations["iragi_reconciliation"]
    source_rows = fixture["reconciliation_rows_per_source"]
    overlap_start = source_rows // 2
    expected_matches = source_rows - overlap_start
    expected_conflicts = (source_rows - 1) // 10 - (overlap_start - 1) // 10
    check("Reconciliation", "matched keys", reconciliation["matched"], expected_matches)
    check("Reconciliation", "source A orphans", reconciliation["orphans_a"], overlap_start)
    check("Reconciliation", "source B orphans", reconciliation["orphans_b"], overlap_start)
    check("Reconciliation", "amount conflicts", reconciliation["conflict_counts"].get("amount", 0), expected_conflicts)

    pdf = results.get("pdf", {})
    if pdf:
        for key, label in (
            ("pymupdf_text_only", "PyMuPDF"),
            ("iragi_extract_text", "Iragi extraction"),
            ("iragi_page_stream", "Iragi page stream"),
        ):
            check(f"PDF {label}", "page count", pdf[key]["pages"], fixture["pdf_pages"])
            check(f"PDF {label}", "fixture text markers", pdf[key]["page_markers"], fixture["pdf_pages"])
        digest_values = [pdf[key]["text_sha256"] for key in (
            "pymupdf_text_only", "iragi_extract_text", "iragi_page_stream"
        )]
        check("PDF text parity", "normalized text hashes agree", len(set(digest_values)) == 1, True)

    workloads = {}
    for name, checks in workload_checks.items():
        passed = sum(item["passed"] for item in checks)
        workloads[name] = {
            "score_percent": round(100 * passed / len(checks), 2) if checks else 100.0,
            "passed_checks": passed,
            "total_checks": len(checks),
            "checks": checks,
        }
    all_checks = [item for checks in workload_checks.values() for item in checks]
    passed_total = sum(item["passed"] for item in all_checks)
    return {
        "definition": "Exact output assertions against synthetic fixtures with known counts and expected extracted text markers.",
        "limitation": "This score is not general accuracy, a real-world anomaly recall measure, or validation of Iragi's subjective quality score.",
        "score_percent": round(100 * passed_total / len(all_checks), 2) if all_checks else None,
        "passed_checks": passed_total,
        "total_checks": len(all_checks),
        "workloads": workloads,
        "competitor_frameworks_scored": [],
    }


def _comparison_metrics(results: dict[str, Any]) -> dict[str, Any]:
    """Calculate relative timing and allocation ratios from the measured medians."""
    csv_result = results["csv"]
    classic = csv_result["iragi_classic"]
    stream = csv_result["iragi_stream"]
    pandas_only = csv_result["pandas_read_csv"]
    pdf_native = results.get("pdf", {}).get("pymupdf_text_only")
    pdf_iragi = results.get("pdf", {}).get("iragi_extract_text")
    comparisons = {
        "csv_stream_vs_classic_time_ratio": stream["median_seconds"] / classic["median_seconds"],
        "csv_stream_python_traced_peak_change_percent": (
            stream["median_python_traced_peak_bytes"]
            / classic["median_python_traced_peak_bytes"] - 1
        ) * 100,
        "iragi_classic_vs_pandas_parse_time_ratio": (
            classic["median_seconds"] / pandas_only["median_seconds"]
        ),
        "iragi_jsonl_stream_vs_pandas_parse_time_ratio": (
            results["jsonl"]["iragi_jsonl_stream"]["median_seconds"]
            / results["jsonl"]["pandas_read_jsonl"]["median_seconds"]
        ),
        "iragi_excel_stream_vs_classic_time_ratio": (
            results["excel"]["iragi_excel_stream"]["median_seconds"]
            / results["excel"]["iragi_excel_classic"]["median_seconds"]
        ),
    }
    if pdf_native and pdf_iragi:
        comparisons["iragi_pdf_vs_pymupdf_time_ratio"] = (
            pdf_iragi["median_seconds"] / pdf_native["median_seconds"]
        )
        comparisons["pdf_normalized_text_matches"] = (
            pdf_iragi["text_sha256"]
            == pdf_native["text_sha256"]
            == results["pdf"]["iragi_page_stream"]["text_sha256"]
        )
        comparisons["iragi_pdf_page_stream_vs_full_time_ratio"] = (
            results["pdf"]["iragi_page_stream"]["median_seconds"]
            / pdf_iragi["median_seconds"]
        )
    return comparisons


def _write_chart(report: dict[str, Any], output: Path) -> None:
    """Write a dependency-free SVG chart from the benchmark JSON structure."""
    csv_results = report["results"]["csv"]
    sections: list[tuple[str, str, list[tuple[str, float]]]] = [
        (
            "CSV elapsed time · seconds · lower is faster",
            "Pandas read_csv parses only; Iragi modes also profile and score.",
            [
                ("Pandas parse only", csv_results["pandas_read_csv"]["median_seconds"]),
                ("Iragi classic scan", csv_results["iragi_classic"]["median_seconds"]),
                ("Iragi chunked scan", csv_results["iragi_stream"]["median_seconds"]),
            ],
        ),
        (
            "CSV Python-traced peak allocation · MiB · lower is less",
            "Excludes native allocations; stream retains row hashes for duplicate counts.",
            [
                (
                    "Pandas parse only",
                    csv_results["pandas_read_csv"]["median_python_traced_peak_bytes"] / (1024**2),
                ),
                (
                    "Iragi classic scan",
                    csv_results["iragi_classic"]["median_python_traced_peak_bytes"] / (1024**2),
                ),
                (
                    "Iragi chunked scan",
                    csv_results["iragi_stream"]["median_python_traced_peak_bytes"] / (1024**2),
                ),
            ],
        ),
    ]
    results = report["results"]
    for workload, title, keys in (
        ("jsonl", "JSON Lines · elapsed time", ("pandas_read_jsonl", "iragi_jsonl_stream")),
        ("excel", "Excel · elapsed time", ("iragi_excel_classic", "iragi_excel_stream")),
        ("pdf", "PDF · elapsed time", ("pymupdf_text_only", "iragi_extract_text", "iragi_page_stream")),
    ):
        values = results.get(workload, {})
        if values:
            labels = {
                "pandas_read_jsonl": "Pandas read_json (parse only)",
                "iragi_jsonl_stream": "Iragi JSONL stream scan",
                "iragi_excel_classic": "Iragi full Excel scan",
                "iragi_excel_stream": "Iragi chunked Excel scan",
                "pymupdf_text_only": "PyMuPDF text only",
                "iragi_extract_text": "Iragi full extraction",
                "iragi_page_stream": "Iragi page iterator",
            }
            note = {
                "jsonl": "Pandas parses only; Iragi also profiles and scores.",
                "excel": f"Same {report['fixture']['excel_rows']:,}-row workbook; both modes run Iragi profiling.",
                "pdf": "100-page synthetic PDF; streaming page iterator avoids retaining all page models.",
            }[workload]
            sections.append((
                title,
                note,
                [(labels[key], values[key]["median_seconds"]) for key in keys if key in values],
            ))
            if workload in {"jsonl", "excel", "pdf"}:
                sections.append((
                    f'{title.split(" · ")[0]} · Python-traced peak allocation · MiB',
                    "Excludes native allocations; this is not total process RAM.",
                    [
                        (
                            labels[key],
                            values[key]["median_python_traced_peak_bytes"] / (1024**2),
                        )
                        for key in keys if key in values
                    ],
                ))
    operation_results = results.get("operations", {})
    if operation_results:
        sections.append((
            "Other Iragi operations · elapsed time",
            "Separate workloads; these bars show their measured cost, not a cross-operation ranking.",
            [(label, operation_results[key]["median_seconds"]) for key, label in (
                ("iragi_contract_validation", "Contract rule validation"),
                ("iragi_auto_clean_dlq", "Auto-clean + DLQ quarantine"),
                ("iragi_reconciliation", "Two-source reconciliation"),
            )],
        ))

    width, section_height = 960, 158
    height = 105 + section_height * len(sections) + 20
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Iragi benchmark comparison</title>',
        '<desc id="desc">Median runtimes for Iragi profiling, contracts, cleaning, reconciliation, PDF extraction and large-file streaming workloads.</desc>',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#172033}.title{font-size:24px;font-weight:700}.subtitle{font-size:13px;fill:#475569}.heading{font-size:16px;font-weight:700}.note{font-size:11px;fill:#475569}.label{font-size:12px}.value{font-size:12px;font-weight:700}.track{fill:#e2e8f0}.bar0{fill:#64748b}.bar1{fill:#2563eb}.bar2{fill:#0f766e}</style>',
        f'<text x="32" y="38" class="title">Iragi {html.escape(report["environment"]["iragi"])} benchmark</text>',
        f'<text x="32" y="61" class="subtitle">{report["repeat"]} independent timed processes per mode; median shown · one warm-up per mode</text>',
    ]
    for section_index, (heading, note, values) in enumerate(sections):
        top = 72 + section_index * section_height
        max_value = max(value for _, value in values) or 1.0
        parts.extend(
            [
                f'<text x="32" y="{top + 20}" class="heading">{html.escape(heading)}</text>',
                f'<text x="32" y="{top + 39}" class="note">{html.escape(note)}</text>',
            ]
        )
        label_x, bar_x, bar_width = 40, 320, 455
        for row, (label, value) in enumerate(values):
            y = top + 65 + row * 29
            shown_width = max(2.0, bar_width * value / max_value)
            color_class = f"bar{min(row, 2)}"
            unit = "MiB" if "MiB" in heading else "s"
            parts.extend(
                [
                    f'<text x="{label_x}" y="{y + 13}" class="label">{html.escape(label)}</text>',
                    f'<rect x="{bar_x}" y="{y}" width="{bar_width}" height="17" rx="4" class="track"/>',
                    f'<rect x="{bar_x}" y="{y}" width="{shown_width:.1f}" height="17" rx="4" class="{color_class}"/>',
                    f'<text x="{bar_x + bar_width + 12}" y="{y + 13}" class="value">{value:.3f} {unit}</text>',
                ]
            )
    parts.append("</svg>")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _write_capability_chart(report: dict[str, Any], output: Path, french: bool = False) -> None:
    """Draw the cross-tool feature matrix as a standalone SVG chart."""
    tools = ["Iragi", "Great Expectations", "Pandera", "ydata-profiling", "Soda Core"]
    translations = {
        "Profiling": "Profilage",
        "Contracts / rules": "Contrats / règles",
        "PDF extraction": "Extraction PDF",
        "Reconciliation": "Réconciliation",
        "Auto-clean + DLQ": "Auto-nettoyage + DLQ",
        "Large-file streaming": "Streaming gros fichiers",
    }
    labels = {"Yes": "Oui", "Partial": "Partiel", "No": "Non"} if french else {
        "Yes": "Yes", "Partial": "Partial", "No": "No"
    }
    width, height = 1290, 390
    row_label_width = 240
    cell_width = (width - row_label_width - 30) // len(tools)
    top = 98
    row_height = 44
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{ "Comparaison des fonctionnalités" if french else "Feature comparison" }</title>',
        f'<desc id="desc">{ "Comparaison fonctionnelle d’Iragi et de quatre outils associés." if french else "Feature comparison of Iragi and four related data tools." }</desc>',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#172033}.title{font-size:24px;font-weight:700}.note{font-size:12px;fill:#475569}.head{font-size:13px;font-weight:700}.row{font-size:13px;font-weight:600}.cell{font-size:12px;font-weight:700}.yes{fill:#dcfce7}.partial{fill:#fef3c7}.no{fill:#e2e8f0}</style>',
        f'<text x="24" y="36" class="title">{ "Comparaison des fonctionnalités" if french else "Feature comparison" }</text>',
        f'<text x="24" y="59" class="note">{ "Présence native ; Partiel indique une prise en charge indirecte, par lots ou avec du code personnalisé." if french else "Native support; Partial means indirect, batch-based, or custom-code support." }</text>',
    ]
    for col, tool in enumerate(tools):
        x = row_label_width + col * cell_width
        parts.append(f'<text x="{x + 5}" y="88" class="head">{html.escape(tool)}</text>')
    for row, capability in enumerate(_CAPABILITIES):
        y = top + row * row_height
        name = translations[capability["name"]] if french else capability["name"]
        parts.append(f'<text x="24" y="{y + 25}" class="row">{html.escape(name)}</text>')
        for col, tool in enumerate(tools):
            value = capability["values"][tool]
            x = row_label_width + col * cell_width
            style = {"Yes": "yes", "Partial": "partial", "No": "no"}[value]
            parts.extend([
                f'<rect x="{x}" y="{y}" width="{cell_width - 8}" height="34" rx="5" class="{style}"/>',
                f'<text x="{x + 8}" y="{y + 22}" class="cell">{labels[value]}</text>',
            ])
    parts.append("</svg>")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _write_accuracy_chart(truth: dict[str, Any], output: Path) -> None:
    """Render exact-match scores from the known-answer fixture checks."""
    rows = list(truth["workloads"].items())
    width, row_height = 960, 30
    height = 158 + row_height * (len(rows) + 1)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Ground-truth benchmark score</title>',
        '<desc id="desc">Exact-match scores against counts and text markers seeded into synthetic benchmark fixtures.</desc>',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#172033}.title{font-size:23px;font-weight:700}.note{font-size:12px;fill:#475569}.label{font-size:12px}.value{font-size:12px;font-weight:700}.track{fill:#e2e8f0}.bar{fill:#0f766e}</style>',
        '<text x="28" y="36" class="title">Known-answer correctness checks</text>',
        f'<text x="28" y="59" class="note">Overall: {truth["score_percent"]:.1f}% · {truth["passed_checks"]}/{truth["total_checks"]} exact checks passed</text>',
        '<text x="28" y="78" class="note">Synthetic fixtures only; this is not a general accuracy or real-world anomaly recall guarantee.</text>',
    ]
    values = [(name, data["score_percent"], data["passed_checks"], data["total_checks"]) for name, data in rows]
    values.append(("Overall", truth["score_percent"], truth["passed_checks"], truth["total_checks"]))
    for index, (name, score, passed, total) in enumerate(values):
        y = 96 + index * row_height
        bar_width = 500 * (score or 0) / 100
        parts.extend([
            f'<text x="28" y="{y + 14}" class="label">{html.escape(name)}</text>',
            f'<rect x="300" y="{y}" width="500" height="18" rx="4" class="track"/>',
            f'<rect x="300" y="{y}" width="{bar_width:.1f}" height="18" rx="4" class="bar"/>',
            f'<text x="812" y="{y + 14}" class="value">{score:.1f}% ({passed}/{total})</text>',
        ])
    parts.append("</svg>")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--chunksize", type=int, default=10_000)
    parser.add_argument("--excel-rows", type=int, default=25_000)
    parser.add_argument("--reconcile-rows", type=int, default=10_000)
    parser.add_argument("--repeat", type=int, default=5, help="Independent timed processes per mode.")
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results.json"))
    parser.add_argument("--chart", type=Path, default=Path("benchmarks/benchmark.svg"))
    parser.add_argument("--accuracy-chart", type=Path, default=Path("benchmarks/accuracy.svg"))
    parser.add_argument("--capability-chart-en", type=Path, default=Path("benchmarks/capabilities_en.svg"))
    parser.add_argument("--capability-chart-fr", type=Path, default=Path("benchmarks/capabilities_fr.svg"))
    parser.add_argument("--child", choices=(
        "pandas", "classic", "stream", "jsonl_pandas", "jsonl_stream",
        "excel_classic", "excel_stream", "contract", "auto_clean_dlq",
        "reconcile", "pdf_pymupdf", "pdf_iragi", "pdf_pages",
    ))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--other-input", type=Path)
    args = parser.parse_args()

    if args.child:
        print(json.dumps(_child(args.child, args.input, args.chunksize, args.other_input)))
        return
    if (
        args.rows <= 0 or args.repeat <= 0 or args.chunksize <= 0
        or args.excel_rows <= 0 or args.reconcile_rows <= 0
    ):
        parser.error("--rows, --excel-rows, --reconcile-rows, --repeat and --chunksize must be positive")
    from iragi import __version__ as iragi_version

    unique_rows = max(1, args.rows - args.rows // 10)
    excel_rows = min(args.rows, args.excel_rows)
    reconcile_rows = min(args.rows, args.reconcile_rows)
    with tempfile.TemporaryDirectory(prefix="iragi-bench-") as temp_dir:
        csv_path = Path(temp_dir) / "benchmark.csv"
        jsonl_path = Path(temp_dir) / "benchmark.jsonl"
        with csv_path.open("w", encoding="utf-8", newline="") as output:
            output.write("record_id,region,amount\n")
            with jsonl_path.open("w", encoding="utf-8") as jsonl_output:
                for row in range(args.rows):
                    logical_id = row if row < unique_rows else row - unique_rows
                    region = f"region-{logical_id % 20}"
                    amount = logical_id % 10_000
                    output.write(f"{logical_id},{region},{amount}\n")
                    jsonl_output.write(json.dumps({
                        "record_id": logical_id, "region": region, "amount": amount
                    }, separators=(",", ":")) + "\n")

        source_a = Path(temp_dir) / "source_a.csv"
        source_b = Path(temp_dir) / "source_b.csv"
        with source_a.open("w", encoding="utf-8", newline="") as out_a, source_b.open(
            "w", encoding="utf-8", newline=""
        ) as out_b:
            out_a.write("record_id,amount\n")
            out_b.write("record_id,amount\n")
            for row in range(reconcile_rows):
                out_a.write(f"{row},{row % 10000}\n")
                other_id = row + reconcile_rows // 2
                amount = other_id % 10000 + (1 if other_id % 10 == 0 else 0)
                out_b.write(f"{other_id},{amount}\n")

        excel_path = Path(temp_dir) / "benchmark.xlsx"
        excel_unique_rows = max(1, excel_rows - excel_rows // 10)
        excel_ids = [
            i if i < excel_unique_rows else i - excel_unique_rows
            for i in range(excel_rows)
        ]
        excel_frame = pd.DataFrame({
            "record_id": excel_ids,
            "region": [f"region-{i % 20}" for i in excel_ids],
            "amount": [i % 10_000 for i in excel_ids],
        })
        excel_frame.to_excel(excel_path, index=False)

        modes: list[tuple[str, str, Path, Path | None]] = [
            ("pandas_read_csv", "pandas", csv_path, None),
            ("iragi_classic", "classic", csv_path, None),
            ("iragi_stream", "stream", csv_path, None),
            ("pandas_read_jsonl", "jsonl_pandas", jsonl_path, None),
            ("iragi_jsonl_stream", "jsonl_stream", jsonl_path, None),
            ("iragi_excel_classic", "excel_classic", excel_path, None),
            ("iragi_excel_stream", "excel_stream", excel_path, None),
            ("iragi_contract_validation", "contract", csv_path, None),
            ("iragi_auto_clean_dlq", "auto_clean_dlq", csv_path, None),
            ("iragi_reconciliation", "reconcile", source_a, source_b),
        ]
        pdf_path = Path(temp_dir) / "benchmark.pdf"
        try:
            import pymupdf

            document = pymupdf.open()
            for page_number in range(100):
                page = document.new_page()
                page.insert_text((72, 72), f"Iragi benchmark page {page_number}: " + ("sample text " * 40))
            document.save(pdf_path)
            document.close()
            modes.extend(
                [
                    ("pymupdf_text_only", "pdf_pymupdf", pdf_path, None),
                    ("iragi_extract_text", "pdf_iragi", pdf_path, None),
                    ("iragi_page_stream", "pdf_pages", pdf_path, None),
                ]
            )
        except ImportError:
            pdf_path = None

        samples: dict[str, list[dict[str, Any]]] = {key: [] for key, _mode, _path, _other in modes}
        # Warm each implementation once without including that sample in the report.
        for _key, mode, path, other in modes:
            _run_child(mode, path, args.chunksize, other)
        # Rotate order to reduce systematic cache/order effects between modes.
        for repeat_index in range(args.repeat):
            order = modes[repeat_index % len(modes):] + modes[:repeat_index % len(modes)]
            for key, mode, path, other in order:
                samples[key].append(_run_child(mode, path, args.chunksize, other))

    results = {key: _summarize(value) for key, value in samples.items()}
    if "pymupdf_text_only" in results:
        pdf_text_matches = (
            results["pymupdf_text_only"]["text_sha256"]
            == results["iragi_page_stream"]["text_sha256"]
            == results["iragi_extract_text"]["text_sha256"]
        )
    else:
        pdf_text_matches = None
    grouped_results = {
        "csv": {key: results[key] for key in ("pandas_read_csv", "iragi_classic", "iragi_stream")},
        "jsonl": {key: results[key] for key in ("pandas_read_jsonl", "iragi_jsonl_stream")},
        "excel": {key: results[key] for key in ("iragi_excel_classic", "iragi_excel_stream")},
        "operations": {key: results[key] for key in (
            "iragi_contract_validation", "iragi_auto_clean_dlq", "iragi_reconciliation"
        )},
    }
    if pdf_text_matches is not None:
        grouped_results["pdf"] = {key: results[key] for key in (
            "pymupdf_text_only", "iragi_extract_text", "iragi_page_stream"
        )}
    fixture = {
        "csv_rows": args.rows,
        "csv_expected_duplicate_rows": args.rows - unique_rows,
        "jsonl_rows": args.rows,
        "excel_rows": excel_rows,
        "reconciliation_rows_per_source": reconcile_rows,
        "pdf_pages": 100 if pdf_text_matches is not None else None,
    }
    truth = _ground_truth_report(grouped_results, fixture)
    report = {
        "fixture": {
            **fixture,
            "csv_columns": 3,
            "csv_duplicate_rate_percent": (args.rows - unique_rows) / args.rows * 100,
        },
        "repeat": args.repeat,
        "warmups_per_mode": 1,
        "chunksize": args.chunksize,
        "environment": {
            "iragi": iragi_version,
            "python": sys.version.split()[0],
            "pandas": pd.__version__,
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
        },
        "framework_comparison": _framework_inventory(),
        "capability_matrix": list(_CAPABILITIES),
        "method_notes": [
            "Each timed sample runs in a fresh subprocess after an unmeasured warm-up; library imports are excluded.",
            "Pandas read_csv is a parser-only baseline; Iragi scans also profile, score and count duplicates.",
            "JSONL compares pandas parsing with Iragi streaming profiling; these operations do different work.",
            "Excel compares full and chunked Iragi scans of the same generated workbook.",
            "Contract validation and auto-clean with quarantine use the 100,000-row CSV fixture; reconciliation uses two separate 10,000-row CSV fixtures. Compare each operation on its own terms.",
            "PDF compares PyMuPDF text-only, full Iragi extraction, and Iragi page iteration; normalized SHA-256 checks text equality.",
            "Python-traced peak excludes native allocations and is not total process RAM.",
            "Medians, min/max and raw samples are reported; results describe this machine and fixture only.",
            "Ground-truth score is the percentage of exact seeded-output checks passed, not general accuracy or validation of the quality score.",
            "The framework capability matrix is descriptive; competitor runtimes are not measured by this Iragi workload suite.",
            "Soda Core's in-memory DataFrame integration requires its pandas adapter and Soda Cloud configuration; no Soda timing is claimed here.",
        ],
        "comparisons": _comparison_metrics(grouped_results),
        "pdf_normalized_text_matches": pdf_text_matches,
        "results": grouped_results,
        "ground_truth": truth,
    }
    serialized = json.dumps(report, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialized, encoding="utf-8")
    _write_chart(report, args.chart)
    _write_accuracy_chart(truth, args.accuracy_chart)
    _write_capability_chart(report, args.capability_chart_en)
    _write_capability_chart(report, args.capability_chart_fr, french=True)
    print(serialized, end="")
    print(f"Wrote chart to {args.chart}", file=sys.stderr)
    print(f"Wrote accuracy chart to {args.accuracy_chart}", file=sys.stderr)
    print(f"Wrote capability charts to {args.capability_chart_en} and {args.capability_chart_fr}", file=sys.stderr)


if __name__ == "__main__":
    main()
