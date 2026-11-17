#!/usr/bin/env python3
"""Compare pandas and Iragi CSV/PDF workloads with repeatable local timings.

Run ``python bench_suite.py --rows 100000 --repeat 5``. The command writes
``benchmarks/results.json`` and ``benchmarks/benchmark.svg`` by default.

Each timed sample runs in a fresh process after one unmeasured warm-up for that
mode. Timings exclude imports. The memory metric is Python-traced allocation;
native allocations in pandas, NumPy and PyMuPDF are not included. Results are
descriptive measurements for the recorded machine, not performance guarantees.
"""

from __future__ import annotations

import argparse
import hashlib
import html
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


def _normalized_digest(text: str) -> tuple[str, int]:
    """Return a whitespace-normalized text digest and its normalized length."""
    normalized = " ".join(text.split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return digest, len(normalized)


def _child(mode: str, input_path: Path, chunksize: int) -> dict[str, Any]:
    """Run one workload sample, timing work but excluding library imports."""
    if mode == "classic" or mode == "stream":
        import iragi
    elif mode == "pdf_pymupdf":
        import pymupdf
    elif mode == "pdf_iragi":
        import pymupdf  # noqa: F401 - warm the shared PDF engine before timing
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
    elif mode == "pdf_pymupdf":
        with pymupdf.open(input_path) as document:
            page_count = len(document)
            text = "\n".join(page.get_text() for page in document)
        digest, characters = _normalized_digest(text)
        summary = {"pages": page_count, "characters": characters, "text_sha256": digest}
    elif mode == "pdf_iragi":
        result = extract(input_path, extract_tables=False)
        digest, characters = _normalized_digest(result.full_text)
        summary = {"pages": result.page_count, "characters": characters, "text_sha256": digest}
    else:
        raise ValueError(f"Unsupported benchmark mode: {mode}")

    seconds = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"seconds": seconds, "python_traced_peak_bytes": peak, **summary}


def _run_child(mode: str, input_path: Path, chunksize: int) -> dict[str, Any]:
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
    }
    if pdf_native and pdf_iragi:
        comparisons["iragi_pdf_vs_pymupdf_time_ratio"] = (
            pdf_iragi["median_seconds"] / pdf_native["median_seconds"]
        )
        comparisons["pdf_normalized_text_matches"] = (
            pdf_iragi["text_sha256"] == pdf_native["text_sha256"]
        )
    return comparisons


def _write_chart(report: dict[str, Any], output: Path) -> None:
    """Write a dependency-free SVG chart from the benchmark JSON structure."""
    csv_results = report["results"]["csv"]
    pdf_results = report["results"].get("pdf", {})
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
    if pdf_results:
        sections.append(
            (
                "PDF elapsed time · seconds · lower is faster",
                "100-page fixture; normalized text SHA-256 is checked for equality.",
                [
                    ("PyMuPDF text only", pdf_results["pymupdf_text_only"]["median_seconds"]),
                    ("Iragi extract (tables off)", pdf_results["iragi_extract_text"]["median_seconds"]),
                ],
            )
        )

    width, section_height = 960, 170
    height = 105 + section_height * len(sections) + 30
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Iragi benchmark comparison</title>',
        '<desc id="desc">Median CSV and PDF elapsed time and Python-traced memory for the recorded benchmark fixture.</desc>',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#172033}.title{font-size:24px;font-weight:700}.subtitle{font-size:13px;fill:#475569}.heading{font-size:16px;font-weight:700}.note{font-size:11px;fill:#475569}.label{font-size:12px}.value{font-size:12px;font-weight:700}.track{fill:#e2e8f0}.bar0{fill:#64748b}.bar1{fill:#2563eb}.bar2{fill:#0f766e}</style>',
        '<text x="32" y="38" class="title">Iragi 0.6.3 benchmark comparison</text>',
        f'<text x="32" y="61" class="subtitle">{report["repeat"]} independent timed processes per mode; median shown · one warm-up per mode</text>',
    ]
    for section_index, (heading, note, values) in enumerate(sections):
        top = 80 + section_index * section_height
        max_value = max(value for _, value in values) or 1.0
        parts.extend(
            [
                f'<text x="32" y="{top + 20}" class="heading">{html.escape(heading)}</text>',
                f'<text x="32" y="{top + 39}" class="note">{html.escape(note)}</text>',
            ]
        )
        label_x, bar_x, bar_width = 40, 280, 500
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--chunksize", type=int, default=10_000)
    parser.add_argument("--repeat", type=int, default=5, help="Independent timed processes per mode.")
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results.json"))
    parser.add_argument("--chart", type=Path, default=Path("benchmarks/benchmark.svg"))
    parser.add_argument("--child", choices=("pandas", "classic", "stream", "pdf_pymupdf", "pdf_iragi"))
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()

    if args.child:
        print(json.dumps(_child(args.child, args.input, args.chunksize)))
        return
    if args.rows <= 0 or args.repeat <= 0 or args.chunksize <= 0:
        parser.error("--rows, --repeat and --chunksize must be positive")

    unique_rows = max(1, args.rows - args.rows // 10)
    with tempfile.TemporaryDirectory(prefix="iragi-bench-") as temp_dir:
        csv_path = Path(temp_dir) / "benchmark.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as output:
            output.write("record_id,region,amount\n")
            for row in range(args.rows):
                logical_id = row if row < unique_rows else row - unique_rows
                output.write(f"{logical_id},region-{logical_id % 20},{logical_id % 10000}\n")

        modes = [("pandas_read_csv", "pandas", csv_path), ("iragi_classic", "classic", csv_path), ("iragi_stream", "stream", csv_path)]
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
                    ("pymupdf_text_only", "pdf_pymupdf", pdf_path),
                    ("iragi_extract_text", "pdf_iragi", pdf_path),
                ]
            )
        except ImportError:
            pdf_path = None

        samples: dict[str, list[dict[str, Any]]] = {key: [] for key, _mode, _path in modes}
        # Warm each implementation once without including that sample in the report.
        for _key, mode, path in modes:
            _run_child(mode, path, args.chunksize)
        # Rotate order to reduce systematic cache/order effects between modes.
        for repeat_index in range(args.repeat):
            order = modes[repeat_index % len(modes):] + modes[:repeat_index % len(modes)]
            for key, mode, path in order:
                samples[key].append(_run_child(mode, path, args.chunksize))

    results = {key: _summarize(value) for key, value in samples.items()}
    if "pymupdf_text_only" in results:
        pdf_text_matches = results["pymupdf_text_only"]["text_sha256"] == results["iragi_extract_text"]["text_sha256"]
    else:
        pdf_text_matches = None
    report = {
        "fixture": {
            "csv_rows": args.rows,
            "csv_columns": 3,
            "csv_expected_duplicate_rows": args.rows - unique_rows,
            "csv_duplicate_rate_percent": (args.rows - unique_rows) / args.rows * 100,
            "pdf_pages": 100 if pdf_text_matches is not None else None,
        },
        "repeat": args.repeat,
        "warmups_per_mode": 1,
        "chunksize": args.chunksize,
        "environment": {
            "iragi": "0.6.3",
            "python": sys.version.split()[0],
            "pandas": pd.__version__,
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
        },
        "method_notes": [
            "Each sample runs in a fresh subprocess; imports are excluded from elapsed time.",
            "Pandas read_csv is a parser-only baseline; Iragi scans also profile, score and count duplicates.",
            "PDF compares PyMuPDF text extraction with Iragi extract(extract_tables=False); normalized SHA-256 checks text equality.",
            "Python-traced peak excludes native allocations and is not total process RAM.",
            "Medians, min/max and raw samples are reported; results describe this machine and fixture only.",
        ],
        "comparisons": _comparison_metrics(
            {"csv": {key: results[key] for key in ("pandas_read_csv", "iragi_classic", "iragi_stream")},
            **({"pdf": {key: results[key] for key in ("pymupdf_text_only", "iragi_extract_text")} } if pdf_text_matches is not None else {})}
        ),
        "pdf_normalized_text_matches": pdf_text_matches,
        "results": {
            "csv": {key: results[key] for key in ("pandas_read_csv", "iragi_classic", "iragi_stream")},
            **({"pdf": {key: results[key] for key in ("pymupdf_text_only", "iragi_extract_text")} } if pdf_text_matches is not None else {}),
        },
    }
    serialized = json.dumps(report, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialized, encoding="utf-8")
    _write_chart(report, args.chart)
    print(serialized, end="")
    print(f"Wrote chart to {args.chart}", file=sys.stderr)


if __name__ == "__main__":
    main()
