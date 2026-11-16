"""Data contract engine for custom business rule validation.

Provides a fluent API to declare column-level rules (not_null, positive,
range, regex) and validate a DataFrame against them, returning structured
ContractViolation entries.

Example:
    >>> import pandas as pd
    >>> from iragi.scan.contract import DataContract, validate_contract
    >>> df = pd.DataFrame({"price": [10.0, -5.0, None]})
    >>> contract = DataContract().require_not_null("price").require_positive("price")
    >>> violations = validate_contract(df, contract)
    >>> len(violations)
    2
"""

from __future__ import annotations

import re
import signal
import threading
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ContractViolation:
    """Represents a single rule violation detected on a DataFrame column.

    :param column: Name of the column that failed the rule.
    :type column: str
    :param rule: Rule identifier (e.g. 'not_null', 'positive', 'regex', 'range').
    :type rule: str
    :param failed_count: Number of rows that violated the rule.
    :type failed_count: int
    :param detail: Human-readable description of the violation.
    :type detail: str

    Example:
        >>> v = ContractViolation(column="price", rule="not_null", failed_count=3, detail="3 null values")
        >>> v.rule
        'not_null'
    """

    column: str
    rule: str
    failed_count: int
    detail: str


@dataclass
class _Rule:
    """Internal representation of a single contract rule.

    :param column: Target column name.
    :type column: str
    :param kind: Rule type identifier.
    :type kind: str
    :param pattern: Regex pattern (for 'regex' rules).
    :type pattern: Optional[str]
    :param min_val: Minimum boundary (for 'range' rules).
    :type min_val: Optional[float]
    :param max_val: Maximum boundary (for 'range' rules).
    :type max_val: Optional[float]
    :param timeout_seconds: Timeout for regex execution (ReDoS protection).
    :type timeout_seconds: float
    """

    column: str
    kind: str
    pattern: Optional[str] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    timeout_seconds: float = 5.0


class DataContract:
    """Fluent builder for declaring column-level data quality rules.

    Rules are accumulated via chained method calls and evaluated in order
    by :func:`validate_contract`.

    Example:
        >>> import pandas as pd
        >>> from iragi.scan.contract import DataContract, validate_contract
        >>> df = pd.DataFrame({"score": [80, 110, -5]})
        >>> contract = DataContract().require_range("score", min_val=0, max_val=100)
        >>> violations = validate_contract(df, contract)
        >>> violations[0].failed_count
        2
    """

    def __init__(self) -> None:
        self._rules: List[_Rule] = []

    def require_not_null(self, column: str) -> "DataContract":
        """Declare that the column must contain no null/NaN values.

        :param column: Column name to enforce.
        :type column: str
        :return: Self, for method chaining.
        :rtype: DataContract

        Example:
            >>> contract = DataContract().require_not_null("email")
        """
        self._rules.append(_Rule(column=column, kind="not_null"))
        return self

    def require_positive(self, column: str) -> "DataContract":
        """Declare that all values in the column must be strictly positive (> 0).

        :param column: Column name to enforce.
        :type column: str
        :return: Self, for method chaining.
        :rtype: DataContract

        Example:
            >>> contract = DataContract().require_positive("price")
        """
        self._rules.append(_Rule(column=column, kind="positive"))
        return self

    def require_range(
        self, column: str, min_val: float, max_val: float
    ) -> "DataContract":
        """Declare that all values must fall within [min_val, max_val] (inclusive).

        :param column: Column name to enforce.
        :type column: str
        :param min_val: Lower bound (inclusive).
        :type min_val: float
        :param max_val: Upper bound (inclusive).
        :type max_val: float
        :return: Self, for method chaining.
        :rtype: DataContract

        Example:
            >>> contract = DataContract().require_range("age", min_val=0, max_val=120)
        """
        self._rules.append(_Rule(column=column, kind="range", min_val=min_val, max_val=max_val))
        return self

    def require_regex(self, column: str, pattern: str, timeout_seconds: float = 5.0) -> "DataContract":
        """Declare that all non-null string values must match the given regex pattern.

        A per-call timeout protects against ReDoS (Regular Expression Denial of Service)
        caused by catastrophic backtracking patterns.

        :param column: Column name to enforce.
        :type column: str
        :param pattern: Python-compatible regular expression.
        :type pattern: str
        :param timeout_seconds: Maximum seconds allowed for regex evaluation (default: 5).
        :type timeout_seconds: float
        :return: Self, for method chaining.
        :rtype: DataContract

        Example:
            >>> contract = DataContract().require_regex("phone", r"^\\+?[0-9]{7,15}$")
        """
        self._rules.append(_Rule(column=column, kind="regex", pattern=pattern, timeout_seconds=timeout_seconds))
        return self


def validate_contract(
    df: "pd.DataFrame",  # noqa: F821
    contract: DataContract,
) -> List[ContractViolation]:
    """Evaluate a DataContract against a DataFrame and return all violations.

    :param df: Target pandas DataFrame to validate.
    :type df: pd.DataFrame
    :param contract: DataContract instance with declared rules.
    :type contract: DataContract
    :return: List of ContractViolation (empty when all rules pass).
    :rtype: List[ContractViolation]
    :raises ValueError: If a rule targets a column that does not exist in the DataFrame.

    Example:
        >>> import pandas as pd
        >>> from iragi.scan.contract import DataContract, validate_contract
        >>> df = pd.DataFrame({"qty": [5, -1, 0]})
        >>> violations = validate_contract(df, DataContract().require_positive("qty"))
        >>> violations[0].failed_count
        2
    """
    import pandas as pd

    violations: List[ContractViolation] = []

    for rule in contract._rules:
        if rule.column not in df.columns:
            raise ValueError(
                f"Contract rule targets column '{rule.column}' which does not exist in DataFrame. "
                f"Available columns: {list(df.columns)}"
            )

        series = df[rule.column]

        if rule.kind == "not_null":
            count = int(series.isna().sum())
            if count > 0:
                violations.append(ContractViolation(
                    column=rule.column,
                    rule="not_null",
                    failed_count=count,
                    detail=f"{count} null value(s) found in column '{rule.column}'.",
                ))

        elif rule.kind == "positive":
            numeric = pd.to_numeric(series, errors="coerce")
            count = int((numeric <= 0).sum())
            if count > 0:
                violations.append(ContractViolation(
                    column=rule.column,
                    rule="positive",
                    failed_count=count,
                    detail=f"{count} non-positive value(s) found in column '{rule.column}' (must be > 0).",
                ))

        elif rule.kind == "range":
            numeric = pd.to_numeric(series, errors="coerce")
            out_of_range = numeric[(numeric < rule.min_val) | (numeric > rule.max_val)]
            count = int(out_of_range.count())
            if count > 0:
                violations.append(ContractViolation(
                    column=rule.column,
                    rule="range",
                    failed_count=count,
                    detail=(
                        f"{count} value(s) in '{rule.column}' fall outside "
                        f"[{rule.min_val}, {rule.max_val}]."
                    ),
                ))

        elif rule.kind == "regex":
            compiled = re.compile(rule.pattern)
            non_null = series.dropna().astype(str)

            # ReDoS protection: use kernel timer to preempt catastrophic backtracking
            has_sigalrm = hasattr(signal, "SIGALRM")
            is_main = threading.current_thread() is threading.main_thread()

            if has_sigalrm and is_main and rule.timeout_seconds > 0:
                def _handle_timeout(signum, frame):
                    raise TimeoutError(
                        f"Regex pattern '{rule.pattern}' on column '{rule.column}' exceeded "
                        f"{rule.timeout_seconds}s timeout — possible ReDoS attack."
                    )

                old_handler = signal.signal(signal.SIGALRM, _handle_timeout)
                signal.setitimer(signal.ITIMER_REAL, rule.timeout_seconds)
                try:
                    mismatches = non_null[~non_null.str.match(compiled)]
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    signal.signal(signal.SIGALRM, old_handler)
            else:
                mismatches = non_null[~non_null.str.match(compiled)]

            count = int(len(mismatches))
            if count > 0:
                violations.append(ContractViolation(
                    column=rule.column,
                    rule="regex",
                    failed_count=count,
                    detail=(
                        f"{count} value(s) in '{rule.column}' do not match "
                        f"pattern '{rule.pattern}'."
                    ),
                ))

    return violations
