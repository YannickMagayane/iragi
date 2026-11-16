"""Unit tests for the Iragi CLI module.

Validates terminal commands for version output, scan execution, and JSON exports.

Example:
    To run this test suite manually:
    $ pytest tests/test_cli.py
"""

import tempfile
from pathlib import Path
from typer.testing import CliRunner
from iragi.cli.main import app

runner = CliRunner()


def test_cli_version_command() -> None:
    """Verify that 'iragi version' outputs the correct semantic version.

    Example:
        >>> res = runner.invoke(app, ["version"])
        >>> assert res.exit_code == 0
    """
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Iragi version:" in result.stdout
    assert "0.1.0" in result.stdout


def test_cli_scan_command_with_csv() -> None:
    """Verify that 'iragi scan' processes a CSV and renders the summary table.

    Example:
        >>> res = runner.invoke(app, ["scan", "sample.csv"])
        >>> assert res.exit_code == 0
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("user,score\nAlice,90\nBob,85\n")
        csv_path = f.name

    result = runner.invoke(app, ["scan", csv_path])
    assert result.exit_code == 0
    assert "Iragi Data Inspection Summary" in result.stdout
    assert "Quality Score:" in result.stdout
    Path(csv_path).unlink()


def test_cli_scan_json_output() -> None:
    """Verify that 'iragi scan --json' returns valid JSON.

    Example:
        >>> res = runner.invoke(app, ["scan", "--json", "data.csv"])
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b\n1,2\n")
        csv_path = f.name

    result = runner.invoke(app, ["scan", "--json", csv_path])
    assert result.exit_code == 0
    assert '"row_count": 1' in result.stdout
    assert '"quality_score"' in result.stdout
    Path(csv_path).unlink()


def test_cli_scan_non_existent_file() -> None:
    """Verify that scanning a missing file exits with error code 1.

    Example:
        >>> res = runner.invoke(app, ["scan", "missing.csv"])
        >>> assert res.exit_code == 1
    """
    result = runner.invoke(app, ["scan", "non_existent_file.csv"])
    assert result.exit_code == 1
    assert "File not found" in result.stdout
