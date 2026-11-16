"""Iragi All module: Unified orchestration of Scan and PDF engines.

Provides high-level analysis pipelines and batch processing.

Example:
    >>> from iragi.all import analyze, batch_analyze
    >>> # result = analyze("data.csv")
"""

from iragi.all.pipeline import analyze, batch_analyze, UnifiedAnalysisResult

__all__ = ["analyze", "batch_analyze", "UnifiedAnalysisResult"]
