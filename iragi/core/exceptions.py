"""Core exceptions for Iragi.

This module defines domain-specific exceptions used across inspection,
cleaning, parsing, and reporting subsystems.

Example:
    >>> from iragi.core.exceptions import IragiDataError
    >>> raise IragiDataError("Invalid tabular data format")
    Traceback (most recent call last):
    ...
    iragi.core.exceptions.IragiDataError: Invalid tabular data format
"""


class IragiError(Exception):
    """Base exception for all Iragi errors.

    Example:
        >>> err = IragiError("Something failed")
        >>> str(err)
        'Something failed'
    """
    pass


class IragiDataError(IragiError):
    """Raised when data inspection or cleaning fails.

    Example:
        >>> err = IragiDataError("Unsupported file type")
        >>> str(err)
        'Unsupported file type'
    """
    pass


class IragiLogError(IragiError):
    """Raised when log parsing or analysis encounters an invalid state.

    Example:
        >>> err = IragiLogError("Failed to parse log line")
        >>> str(err)
        'Failed to parse log line'
    """
    pass


class IragiConfigError(IragiError):
    """Raised when configuration values are missing or invalid.

    Example:
        >>> err = IragiConfigError("Invalid scoring threshold")
        >>> str(err)
        'Invalid scoring threshold'
    """
    pass


class IragiReportError(IragiError):
    """Raised when generating a report fails.

    Example:
        >>> err = IragiReportError("Template rendering failed")
        >>> str(err)
        'Template rendering failed'
    """
    pass
