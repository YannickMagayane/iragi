import importlib
import subprocess
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest

import iragi
from iragi.core.exceptions import IragiDataError
from iragi.scan.contract import DataContract, validate_contract
from iragi.scan.engine import scan_csv_stream
from iragi.scan.engine import scan_excel_stream
from iragi.scan.readers import _check_zip_bomb
from iragi.scan.readers import read_csv_file
from iragi.scan.readers import read_excel_file
from iragi.scan.cleaner import auto_clean


def test_scan_module_import_path_and_callable_compatibility():
    import iragi.scan.engine as engine

    assert engine is importlib.import_module("iragi.scan.engine")
    assert callable(iragi.scan)


def test_package_imports_when_pillow_is_unavailable():
    code = "import sys; sys.modules['PIL'] = None; import iragi.scan.engine as engine; import iragi; import iragi.pdf.ocr; assert callable(iragi.scan); assert engine.__name__ == 'iragi.scan.engine'"
    subprocess.run([sys.executable, "-c", code], check=True)


@pytest.mark.parametrize("rule", ["positive", "range"])
def test_numeric_contracts_reject_non_numeric_non_null_values(rule):
    df = pd.DataFrame({"amount": ["invalid", None, "12"]})
    contract = (
        DataContract().require_positive("amount")
        if rule == "positive"
        else DataContract().require_range("amount", min_val=1, max_val=20)
    )
    violation, = validate_contract(df, contract)
    assert violation.failed_count == 1


def test_zip_xml_inspection_does_not_read_member_into_memory(tmp_path, monkeypatch):
    archive = tmp_path / "valid.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("doc.xml", "<root>" + ("<item/>" * 10000) + "</root>")

    def forbidden_read(*args, **kwargs):
        raise AssertionError("ZipFile.read would materialize the complete member")

    monkeypatch.setattr(zipfile.ZipFile, "read", forbidden_read)
    _check_zip_bomb(archive)


def test_zip_xml_entity_expansion_is_rejected(tmp_path):
    archive = tmp_path / "malicious.zip"
    payload = b" " * 5000 + b'<!DOCTYPE root [<!ENTITY x "boom">]><root>&x;</root>'
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("doc.xml", payload)
    with pytest.raises(IragiDataError, match="Unsafe XML"):
        _check_zip_bomb(archive)


def test_stream_scan_counts_duplicates_and_marks_score_estimated(tmp_path):
    csv = tmp_path / "duplicates.csv"
    csv.write_text("id,value\n1,a\n2,b\n1,a\n", encoding="utf-8")
    result = scan_csv_stream(csv, chunksize=1)
    assert result.duplicate_rows_count == 1
    assert result.score_is_estimated is True


def test_excel_stream_counts_duplicates_and_marks_score_estimated(tmp_path):
    path = tmp_path / "duplicates.xlsx"
    pd.DataFrame({"id": [1, 2, 1], "value": ["a", "b", "a"]}).to_excel(path, index=False)
    result = scan_excel_stream(path, chunksize=1)
    assert result.duplicate_rows_count == 1
    assert result.score_is_estimated is True


def test_classic_csv_read_probes_then_reads_once_with_c_engine(tmp_path, monkeypatch):
    import iragi.scan.readers as readers

    csv = tmp_path / "sample.csv"
    csv.write_text("id;value\n1;a\n2;b\n", encoding="utf-8")
    real_read_csv = readers.pd.read_csv
    calls = []

    def tracking_read_csv(*args, **kwargs):
        calls.append((kwargs.get("engine"), kwargs.get("nrows")))
        return real_read_csv(*args, **kwargs)

    monkeypatch.setattr(readers.pd, "read_csv", tracking_read_csv)
    result = read_csv_file(csv)
    assert result.shape == (2, 2)
    assert calls == [("c", None)]


def test_excel_reader_sanitizes_formula_like_strings_by_default(tmp_path):
    path = tmp_path / "formula.xlsx"
    pd.DataFrame({"value": ["+SUM(1,2)", "safe"]}).to_excel(path, index=False)
    result = read_excel_file(path)
    assert result["value"].tolist() == ["SUM(1,2)", "safe"]


def test_auto_clean_sanitizes_formula_like_strings_by_default():
    result = auto_clean(pd.DataFrame({"value": ["=CMD()"]}), drop_duplicates=False)
    assert result.df.loc[0, "value"] == "CMD()"


def test_json_lines_scan_streams_and_counts_duplicates(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text('{"id":1,"value":"a"}\n{"id":2,"value":"b"}\n{"id":1,"value":"a"}\n', encoding="utf-8")
    result = iragi.scan(path, stream=True, chunksize=1)
    assert result.row_count == 3
    assert result.duplicate_rows_count == 1
    assert result.score_is_estimated is True


def test_json_lines_stream_handles_columns_added_in_later_chunks(tmp_path):
    path = tmp_path / "changing-schema.jsonl"
    path.write_text('{"left":1}\n{"right":2}\n', encoding="utf-8")
    result = iragi.scan(path, stream=True, chunksize=1)
    assert result.row_count == 2
    assert result.column_count == 2
    assert result.missing_values_count == 2
