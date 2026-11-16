"""Unit tests for the Iragi core module.

Validates core configuration defaults, custom domain models, and exception handling.

Example:
    To run this test suite manually:
    $ pytest tests/test_core.py
"""

from pathlib import Path
import pytest
import iragi
from iragi.core.config import IragiConfig, get_default_config
from iragi.core.exceptions import IragiError, IragiDataError
from iragi.core.models import QualityScore, ColumnProfile, DataInspectionResult


def test_iragi_version() -> None:
    """Validate that the package version string is defined and non-empty.

    Example:
        >>> import iragi
        >>> assert iragi.__version__ == "0.1.0"
    """
    assert hasattr(iragi, "__version__")
    assert iragi.__version__ == "0.1.0"


def test_default_config() -> None:
    """Verify that default runtime configurations initialize with expected values.

    Example:
        >>> cfg = get_default_config()
        >>> assert cfg.outlier_iqr_multiplier == 1.5
    """
    config = get_default_config()
    assert isinstance(config, IragiConfig)
    assert config.missing_penalty_weight == 35.0
    assert config.duplicate_penalty_weight == 25.0
    assert config.outlier_iqr_multiplier == 1.5


def test_quality_score_model() -> None:
    """Verify the creation and breakdown calculation of QualityScore.

    Example:
        >>> score = QualityScore(total_score=95.0, breakdown={"missing": -5.0})
        >>> assert score.total_score == 95.0
    """
    score = QualityScore(
        total_score=85.0,
        breakdown={"missing_penalty": 15.0},
        explanations=["Deducted 15 points due to missing cells in critical columns"],
    )
    assert score.total_score == 85.0
    assert "missing_penalty" in score.breakdown
    assert len(score.explanations) == 1


def test_data_inspection_result() -> None:
    """Verify instantiation of DataInspectionResult and column profiling attachments.

    Example:
        >>> col = ColumnProfile("id", "numeric", 10, 0, 10)
        >>> assert col.name == "id"
    """
    col = ColumnProfile(
        name="sales",
        inferred_type="numeric",
        total_count=100,
        missing_count=2,
        unique_count=80,
    )
    score = QualityScore(total_score=98.0)
    result = DataInspectionResult(
        file_path="sample.csv",
        row_count=100,
        column_count=1,
        missing_values_count=2,
        duplicate_rows_count=0,
        invalid_dates_count=0,
        potential_outliers_count=0,
        quality_score=score,
        column_profiles=[col],
    )
    assert result.row_count == 100
    assert len(result.column_profiles) == 1
    assert result.column_profiles[0].name == "sales"


def test_exceptions_hierarchy() -> None:
    """Verify that domain exceptions inherit properly from IragiError.

    Example:
        >>> assert issubclass(IragiDataError, IragiError)
    """
    assert issubclass(IragiDataError, IragiError)
    with pytest.raises(IragiDataError):
        raise IragiDataError("Parsing failure on corrupted file")
