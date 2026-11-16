"""Command-line interface (CLI) for Iragi.

Provides terminal commands for inspecting files, extracting document content,
and running unified data intelligence pipelines.

Example:
    To run the CLI from terminal:
    $ iragi --help
    $ iragi version
    $ iragi scan data.csv
    $ iragi pdf text document.pdf
    $ iragi all document.pdf
"""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

import iragi
from iragi.scan.engine import scan
from iragi.scan.reports import to_json_report
from iragi.pdf.extractor import extract, extract_text_from_pdf, extract_metadata_from_pdf
from iragi.pdf.tables import extract_tables_from_pdf
from iragi.all.pipeline import analyze, batch_analyze

app = typer.Typer(
    name="iragi",
    help="Iragi: Modular file inspection, extraction, and quality intelligence toolkit.",
    add_completion=False,
)
pdf_app = typer.Typer(help="Extract text, metadata, and tables from PDF documents.")
app.add_typer(pdf_app, name="pdf")

console = Console()


@app.command("version")
def version_cmd() -> None:
    """Display the installed Iragi version.

    Example:
        >>> from typer.testing import CliRunner
        >>> runner = CliRunner()
        >>> result = runner.invoke(app, ["version"])
        >>> "Iragi version" in result.stdout
        True
    """
    console.print(f"[bold cyan]Iragi version:[/bold cyan] {iragi.__version__}")


@app.command("scan")
def scan_cmd(
    file_path: Path = typer.Argument(..., help="Path to CSV, Excel, or JSON file to inspect"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Path to export JSON report"),
    json_only: bool = typer.Option(False, "--json", help="Print raw JSON output instead of rich tables"),
) -> None:
    """Inspect and profile a tabular data file (CSV, Excel, JSON).

    :param file_path: Path to target file.
    :type file_path: Path
    :param output: Optional destination path for JSON report.
    :type output: Optional[Path]
    :param json_only: Output raw JSON to stdout.
    :type json_only: bool

    Example:
        >>> from typer.testing import CliRunner
        >>> runner = CliRunner()
        >>> res = runner.invoke(app, ["scan", "--help"])
        >>> res.exit_code == 0
        True
    """
    if not file_path.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
        raise typer.Exit(code=1)

    try:
        result = scan(file_path)
    except Exception as exc:
        console.print(f"[bold red]Scan error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    if json_only:
        json_output = to_json_report(result, output_path=output)
        console.print(json_output)
        return

    score = result.quality_score.total_score
    score_color = "green" if score >= 80 else ("yellow" if score >= 50 else "red")

    console.print(
        Panel(
            f"[bold]Target File:[/bold] {result.file_path}\n"
            f"[bold]Rows:[/bold] {result.row_count:,} | [bold]Columns:[/bold] {result.column_count} | "
            f"[bold]Duplicates:[/bold] {result.duplicate_rows_count} | [bold]Null Cells:[/bold] {result.missing_values_count}\n"
            f"[bold]Quality Score:[/bold] [{score_color}]{score:.1f} / 100[/{score_color}]",
            title="[bold cyan]Iragi Data Inspection Summary[/bold cyan]",
            border_style="cyan",
        )
    )

    table = Table(title="Column Profiles", border_style="dim")
    table.add_column("Column", style="bold")
    table.add_column("Type", style="magenta")
    table.add_column("Missing", justify="right")
    table.add_column("Unique", justify="right")
    table.add_column("Outliers", justify="right")

    for col in result.column_profiles:
        table.add_row(
            col.name,
            col.inferred_type,
            str(col.missing_count),
            str(col.unique_count),
            str(col.outliers_count),
        )

    console.print(table)

    if result.recommendations:
        console.print("\n[bold yellow]Quality Recommendations:[/bold yellow]")
        for rec in result.recommendations:
            console.print(f" • {rec}")

    if output:
        to_json_report(result, output_path=output)
        console.print(f"\n[bold green]Report saved to:[/bold green] {output}")


@pdf_app.command("text")
def pdf_text_cmd(
    file_path: Path = typer.Argument(..., help="Path to PDF file"),
) -> None:
    """Extract and print raw text from a PDF document."""
    if not file_path.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
        raise typer.Exit(code=1)
    text = extract_text_from_pdf(file_path)
    console.print(text)


@pdf_app.command("metadata")
def pdf_metadata_cmd(
    file_path: Path = typer.Argument(..., help="Path to PDF file"),
) -> None:
    """Read and display metadata properties from a PDF document."""
    if not file_path.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
        raise typer.Exit(code=1)
    meta = extract_metadata_from_pdf(file_path)
    table = Table(title=f"Metadata: {file_path.name}")
    table.add_column("Property", style="bold cyan")
    table.add_column("Value")
    for k, v in meta.items():
        table.add_row(str(k), str(v))
    console.print(table)


@pdf_app.command("tables")
def pdf_tables_cmd(
    file_path: Path = typer.Argument(..., help="Path to PDF file"),
) -> None:
    """Extract and display tabular grids identified inside a PDF document."""
    if not file_path.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
        raise typer.Exit(code=1)
    tables = extract_tables_from_pdf(file_path)
    if not tables:
        console.print("[yellow]No tabular grids detected in document.[/yellow]")
        return
    for tbl in tables:
        df = tbl.to_dataframe()
        console.print(f"\n[bold green]Page {tbl.page_number} - Table #{tbl.table_index + 1}[/bold green]")
        console.print(df)


@app.command("all")
def all_cmd(
    file_path: Path = typer.Argument(..., help="Path to target file or directory"),
    enable_ocr: bool = typer.Option(False, "--ocr", help="Enable Optical Character Recognition on scanned pages"),
) -> None:
    """Execute unified document extraction and quality inspection pipeline."""
    if not file_path.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
        raise typer.Exit(code=1)

    result = analyze(file_path, enable_ocr=enable_ocr)
    score = result.overall_quality_score
    score_color = "green" if score >= 80 else ("yellow" if score >= 50 else "red")

    console.print(
        Panel(
            f"[bold]Target:[/bold] {result.file_path} ({result.file_type.upper()})\n"
            f"[bold]Audited Tables:[/bold] {len(result.tabular_inspections)}\n"
            f"[bold]Overall Quality Score:[/bold] [{score_color}]{score:.1f} / 100[/{score_color}]",
            title="[bold magenta]Iragi Unified Analysis Result[/bold magenta]",
            border_style="magenta",
        )
    )

    if result.recommendations:
        console.print("\n[bold yellow]Consolidated Recommendations:[/bold yellow]")
        for rec in result.recommendations:
            console.print(f" • {rec}")


def main() -> None:
    """Entrypoint function for console scripts execution."""
    app()


if __name__ == "__main__":
    main()
