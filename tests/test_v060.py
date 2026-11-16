"""Unit tests for Iragi v0.6.0 features and resilience hardening.

Tests cover:
1. auto_clean with computed_columns (deterministic business rule imputation).
2. auto_clean with exclude_columns and impute_strategies.
3. auto_clean with DataContract remediation and dead-letter quarantine (DLQ).
4. reconcile and reconcile_multi with key_transform (regex and callable normalization).
5. iter_excel_chunks and scan_excel_stream (bounded-memory streaming for large Excel files).
6. iter_pdf_pages and extract_tables_stream (bounded-memory streaming for large PDF files).
"""

import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from iragi.scan.cleaner import auto_clean, CleaningResult
from iragi.scan.contract import DataContract
from iragi.reconcile.engine import reconcile, reconcile_multi
from iragi.scan.readers import iter_excel_chunks
from iragi.scan.engine import scan_excel_stream
from iragi.pdf.extractor import extract, iter_pdf_pages
from iragi.pdf.tables import extract_tables_stream


# ============================================================================
# Faille 1: Imputation deterministe & Exclusion de colonnes dans auto_clean
# ============================================================================

def test_auto_clean_computed_columns_deterministic_formula():
    """Verify that auto_clean uses deterministic computed formulas instead of blind mean."""
    df = pd.DataFrame({
        "unit_price": [10.0, 20.0, 15.0, 50.0],
        "quantity": [2, 3, 4, 1],
        "discount": [0.0, 0.1, 0.0, 0.2],
        "shipping": [5.0, 5.0, 5.0, 10.0],
        "net_amount": [25.0, None, 65.0, None],  # 2 missing amounts
    })

    # Formula: (unit_price * quantity) * (1 - discount) + shipping
    # Row 1: (20 * 3) * 0.9 + 5 = 54 + 5 = 59.0
    # Row 3: (50 * 1) * 0.8 + 10 = 40 + 10 = 50.0
    computed_rules = {
        "net_amount": lambda d: (d["unit_price"] * d["quantity"]) * (1.0 - d["discount"]) + d["shipping"]
    }

    result = auto_clean(df, computed_columns=computed_rules)
    assert result.df["net_amount"].isna().sum() == 0
    assert result.df.loc[1, "net_amount"] == pytest.approx(59.0)
    assert result.df.loc[3, "net_amount"] == pytest.approx(50.0)
    assert result.changes.get("computed_columns_applied") == ["net_amount"]


def test_auto_clean_exclude_columns_prevents_blind_imputation():
    """Verify that columns in exclude_columns are spared from statistical imputation."""
    df = pd.DataFrame({
        "price": [100.0, None, 300.0],
        "sensitive_financial_col": [1200.0, None, 4500.0],
    })

    result = auto_clean(df, exclude_columns=["sensitive_financial_col"])
    # price should be imputed with mean (200.0)
    assert result.df["price"].isna().sum() == 0
    assert result.df.loc[1, "price"] == pytest.approx(200.0)
    # sensitive_financial_col must remain untouched
    assert result.df["sensitive_financial_col"].isna().sum() == 1


def test_auto_clean_impute_strategies_per_column():
    """Verify per-column imputation strategies (zero, median, mode, or custom value)."""
    df = pd.DataFrame({
        "val_median": [10.0, 20.0, 100.0, None],
        "val_zero": [5.0, None, 15.0, 20.0],
        "val_none": [1.0, None, 3.0, 4.0],
    })

    strategies = {
        "val_median": "median",
        "val_zero": 0.0,
        "val_none": "none",
    }
    result = auto_clean(df, impute_strategies=strategies)
    # Median of [10, 20, 100] is 20.0
    assert result.df.loc[3, "val_median"] == pytest.approx(20.0)
    assert result.df.loc[1, "val_zero"] == pytest.approx(0.0)
    assert result.df["val_none"].isna().sum() == 1


# ============================================================================
# Faille 2: DataContract remediation & Quarantine (DLQ) dans auto_clean
# ============================================================================

def test_auto_clean_with_datacontract_quarantine():
    """Verify that auto_clean quarantines rows violating DataContract rules."""
    df = pd.DataFrame({
        "id": [1, 2, 3, 4],
        "amount": [100.0, -50.0, 300.0, -1250.0],  # 2 negative invalid rows
        "status": ["PAID", "FAILED", "PAID", "INVALID"],
    })

    contract = (
        DataContract()
        .require_positive("amount")
        .require_regex("status", r"^(PAID|FAILED)$")
    )

    result = auto_clean(df, contract=contract, contract_action="quarantine")

    # Cleaned DataFrame must contain only valid rows (ids 1 and 3)
    assert len(result.df) == 2
    assert list(result.df["id"]) == [1, 3]

    # Quarantined rows must be isolated in quarantine_df (ids 2 and 4)
    assert len(result.quarantine_df) == 2
    assert list(result.quarantine_df["id"]) == [2, 4]
    assert result.changes["contract_violations_quarantined"] == 2
    assert len(result.contract_violations) > 0


# ============================================================================
# Faille 3: Normalisation de cles et regex dans reconcile & reconcile_multi
# ============================================================================

def test_reconcile_with_regex_key_transform():
    """Verify reconciliation matches keys with heterogeneous prefixes using regex extraction."""
    # Source A has TRX-10000, Source B has FACT_10000
    df_sales = pd.DataFrame({"order_id": ["TRX-101", "TRX-102", "TRX-103"], "amount": [10, 20, 30]})
    df_finance = pd.DataFrame({"facture_id": ["FACT_101", "FACT_102", "FACT_999"], "amount": [10, 20, 99]})

    # Reconcile using regex to extract digits sequence
    result = reconcile(
        df_sales,
        df_finance,
        on=("order_id", "facture_id"),
        key_transform=r"(\d+)",
        compare_columns=["amount"],
    )

    assert result.matched_count == 2  # 101 and 102
    assert result.orphan_a_count == 1  # TRX-103
    assert result.orphan_b_count == 1  # FACT_999
    assert result.match_rate == pytest.approx(0.5, 0.01)


def test_reconcile_multi_with_key_transform_callable():
    """Verify reconcile_multi reaches consensus across 3 sources using key normalization."""
    df_sales = pd.DataFrame({"ref": ["TRX-10001", "TRX-10002", "TRX-10003"]})
    df_logistics = pd.DataFrame({"ref": ["LOG-10001", "LOG-10002", "LOG-10004"]})
    df_finance = pd.DataFrame({"ref": ["ACC_10001", "ACC_10002", "ACC_10005"]})

    # Strip any prefix and keep digits only
    res = reconcile_multi(
        {"sales": df_sales, "logistics": df_logistics, "finance": df_finance},
        on="ref",
        key_transform=lambda k: "".join(filter(str.isdigit, str(k))),
    )

    assert res.all_matched_count == 2  # 10001 and 10002
    assert res.total_unique_keys == 5  # 10001, 10002, 10003, 10004, 10005
    assert res.orphans_by_source["sales"] == 1  # 10003
    assert res.orphans_by_source["logistics"] == 1  # 10004
    assert res.orphans_by_source["finance"] == 1  # 10005


# ============================================================================
# Faille 4: Streaming pour gros fichiers Excel et PDF
# ============================================================================

def test_iter_excel_chunks_and_scan_excel_stream(tmp_path):
    """Verify streaming chunks from an Excel file without full memory load."""
    excel_path = tmp_path / "large_mock.xlsx"
    rows = [{"id": i, "val": i * 1.5, "cat": "A" if i % 2 == 0 else "B"} for i in range(150)]
    df_src = pd.DataFrame(rows)
    df_src.to_excel(excel_path, index=False)

    # 1. Test iter_excel_chunks yields slices
    chunks = list(iter_excel_chunks(excel_path, chunksize=50))
    assert len(chunks) == 3
    assert len(chunks[0]) == 50
    assert len(chunks[2]) == 50

    # 2. Test scan_excel_stream calculates quality metrics incrementally
    result = scan_excel_stream(excel_path, chunksize=50)
    assert result.row_count == 150
    assert result.column_count == 3
    assert result.quality_score.total_score > 90.0
    assert "id" in result.columns


def test_iter_pdf_pages_and_tables_stream(tmp_path):
    """Verify streaming PDF pages and tables generation."""
    pdf_path = tmp_path / "stream_mock.pdf"

    # Create a small multi-page PDF using PyMuPDF
    import pymupdf as fitz
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((50, 50), f"Page {i+1} Content for streaming test")
    doc.save(pdf_path)
    doc.close()

    # Stream pages one by one
    pages = list(iter_pdf_pages(pdf_path, batch_size=1))
    assert len(pages) == 3
    assert pages[0].page_number == 1
    assert "Page 1 Content" in pages[0].text

    # Extract tables stream returns an iterator
    tables_iter = extract_tables_stream(pdf_path)
    tables = list(tables_iter)
    assert isinstance(tables, list)
