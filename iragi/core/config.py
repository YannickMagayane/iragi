"""Configuration management for Iragi.

Provides system-wide defaults, tunable quality weights, and persistent settings.

Example:
    >>> from iragi.core.config import IragiConfig
    >>> config = IragiConfig()
    >>> config.outlier_iqr_multiplier
    1.5
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class IragiConfig:
    """Runtime configuration options for Iragi analyses.

    :param missing_penalty_weight: Weight deducted for missing cells ratio.
    :type missing_penalty_weight: float
    :param duplicate_penalty_weight: Weight deducted for duplicate rows ratio.
    :type duplicate_penalty_weight: float
    :param outlier_penalty_weight: Weight deducted for numerical outlier ratio.
    :type outlier_penalty_weight: float
    :param invalid_date_penalty_weight: Weight deducted for unparseable dates.
    :type invalid_date_penalty_weight: float
    :param outlier_iqr_multiplier: IQR multiplier used to detect statistical outliers.
    :type outlier_iqr_multiplier: float
    :param db_path: Path to the local SQLite history database.
    :type db_path: Path

    Example:
        >>> cfg = IragiConfig(outlier_iqr_multiplier=2.0)
        >>> cfg.outlier_iqr_multiplier
        2.0
    """

    missing_penalty_weight: float = 35.0
    duplicate_penalty_weight: float = 25.0
    outlier_penalty_weight: float = 20.0
    invalid_date_penalty_weight: float = 20.0
    outlier_iqr_multiplier: float = 1.5
    db_path: Path = Path(os.environ.get("IRAGI_DB_PATH", Path.home() / ".iragi" / "history.db"))


def get_default_config() -> IragiConfig:
    """Retrieve the standard system default configuration.

    :return: An initialized default IragiConfig instance.
    :rtype: IragiConfig

    Example:
        >>> cfg = get_default_config()
        >>> isinstance(cfg, IragiConfig)
        True
    """
    return IragiConfig()
