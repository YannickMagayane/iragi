#!/usr/bin/env python3
"""Reproducible timing and Python-allocation benchmark for Iragi CSV/PDF workflows.

Run with ``python bench_suite.py --rows 100000 --output benchmarks/results.json``.
Peak memory is Python-traced allocation only; native allocations made by pandas
and NumPy are not included.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

import pandas as pd
import iragi


def _child(mode: str, csv_path: Path, chunksize: int) -> dict:
    import pandas as pd

    tracemalloc.start()
    started = time.perf_counter()
    if mode == "pandas":
        result = pd.read_csv(csv_path)
        summary = {"rows": len(result), "columns": len(result.columns)}
    elif mode == "classic":
        import iragi

        result = iragi.scan(csv_path)
        summary = {"rows": result.row_count, "score": result.quality_score.total_score}
    else:
        if mode == "stream":
            import iragi

            result = iragi.scan(csv_path, stream=True, chunksize=chunksize)
            summary = {
                "rows": result.row_count,
                "score": result.quality_score.total_score,
                "duplicate_rows": result.duplicate_rows_count,
                "score_is_estimated": result.score_is_estimated,
            }
        elif mode == "pdf_pymupdf":
            import pymupdf

            with pymupdf.open(csv_path) as document:
                page_count = len(document)
                text = "\n".join(page.get_text() for page in document)
            summary = {"pages": page_count, "characters": len(text)}
        else:
            from iragi.pdf import extract

            result = extract(csv_path, extract_tables=False)
            summary = {"pages": result.page_count, "characters": len(result.full_text)}
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"seconds": round(elapsed, 6), "python_traced_peak_bytes": peak, **summary}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--chunksize", type=int, default=10_000)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child", choices=("pandas", "classic", "stream", "pdf_pymupdf", "pdf_iragi"))
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()

    if args.child:
        print(json.dumps(_child(args.child, args.input, args.chunksize)))
        return

    with tempfile.TemporaryDirectory(prefix="iragi-bench-") as temp_dir:
        csv_path = Path(temp_dir) / "benchmark.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as output:
            output.write("record_id,region,amount\n")
            for row in range(args.rows):
                output.write(f"{row % max(1, args.rows // 10)},region-{row % 20},{row % 10000}\n")

        pdf_path = Path(temp_dir) / "benchmark.pdf"
        modes = ["pandas", "classic", "stream"]
        try:
            import pymupdf

            document = pymupdf.open()
            for page_number in range(100):
                page = document.new_page()
                page.insert_text((72, 72), f"Iragi benchmark page {page_number}: " + ("sample text " * 40))
            document.save(pdf_path)
            document.close()
            modes.extend(("pdf_pymupdf", "pdf_iragi"))
        except ImportError:
            pdf_path = None

        results = {}
        for mode in modes:
            command = [
                sys.executable, __file__, "--child", mode,
                "--input", str(pdf_path if mode.startswith("pdf_") else csv_path),
                "--chunksize", str(args.chunksize),
            ]
            completed = subprocess.run(command, check=True, capture_output=True, text=True)
            results[mode] = json.loads(completed.stdout)

    report = {
        "rows_requested": args.rows,
        "chunksize": args.chunksize,
        "environment": {
            "python": sys.version.split()[0],
            "pandas": pd.__version__,
            "iragi": iragi.__version__,
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
        },
        "measurement_note": "python_traced_peak_bytes excludes native pandas/NumPy allocations; timings are local, not a performance guarantee.",
        "results": results,
    }
    serialized = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")


if __name__ == "__main__":
    main()
