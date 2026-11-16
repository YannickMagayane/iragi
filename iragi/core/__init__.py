"""Iragi core package: configuration, models, exceptions, and remote utilities."""

from iragi.core.config import IragiConfig, get_default_config
from iragi.core.exceptions import IragiDataError, IragiError
from iragi.core.models import DataInspectionResult, QualityScore, ColumnProfile
from iragi.core.remote import is_remote_url, fetch_remote_file, resolve_file_source

__all__ = [
    "IragiConfig",
    "get_default_config",
    "IragiDataError",
    "IragiError",
    "DataInspectionResult",
    "QualityScore",
    "ColumnProfile",
    "is_remote_url",
    "fetch_remote_file",
    "resolve_file_source",
]
