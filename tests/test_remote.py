"""Unit tests for remote URL file fetching and ingestion in Iragi.

Tests cover:
1. is_remote_url identification.
2. fetch_remote_file downloading remote payloads safely with max_bytes and timeout protection.
3. iragi.scan() directly accepting HTTP/HTTPS URLs (e.g. cloud storage or Open Data).
4. iragi.all.analyze() directly accepting HTTP/HTTPS URLs.
5. Error handling for network failures or payload size violations.
"""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from iragi.core.remote import is_remote_url, fetch_remote_file, resolve_file_source
from iragi.core.exceptions import IragiDataError
import iragi


def test_is_remote_url():
    """Verify is_remote_url identifies HTTP, HTTPS, and FTP protocols."""
    assert is_remote_url("https://data.gov/resources/air_quality_2026.csv") is True
    assert is_remote_url("http://s3.amazonaws.com/bucket/genomics_study.parquet") is True
    assert is_remote_url("ftp://server.org/archive/satellites.json") is True
    assert is_remote_url("/var/data/local.csv") is False
    assert is_remote_url(Path("relative/file.xlsx")) is False
    assert is_remote_url("data.csv") is False


def test_fetch_remote_file_success(tmp_path):
    """Verify fetch_remote_file downloads content to a local temporary file with proper suffix."""
    csv_bytes = b"sensor_id,temperature,humidity\nS101,22.4,45.2\nS102,23.1,44.8\n"

    mock_response = MagicMock()
    mock_response.read.side_effect = [csv_bytes, b""]
    mock_response.headers = {"Content-Type": "text/csv"}

    with patch("urllib.request.urlopen", return_value=mock_response):
        local_path, is_temp = resolve_file_source(
            "https://cloud-iot.net/telemetry/sensors_daily.csv"
        )
        assert is_temp is True
        assert local_path.is_file()
        assert local_path.suffix == ".csv"
        content = local_path.read_bytes()
        assert b"S101" in content
        local_path.unlink()


def test_fetch_remote_file_exceeds_max_bytes():
    """Verify fetch_remote_file stops and raises IragiDataError when payload exceeds max_bytes."""
    large_payload = b"A" * 1024

    mock_response = MagicMock()
    mock_response.read.side_effect = [large_payload, large_payload]

    with patch("urllib.request.urlopen", return_value=mock_response):
        with pytest.raises(IragiDataError, match="exceeds maximum allowed limit"):
            fetch_remote_file("https://storage.cloud.org/big_dump.csv", max_bytes=512)


def test_scan_remote_cloud_file_url():
    """Verify iragi.scan inspects remote cloud datasets transparently."""
    csv_data = b"patient_id,blood_pressure,heart_rate\nP-01,120,72\nP-02,135,80\n"

    mock_response = MagicMock()
    mock_response.read.side_effect = [csv_data, b""]
    mock_response.headers = {}

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = iragi.scan("https://opendata.health.org/clinical_cohorts.csv")
        assert result.row_count == 2
        assert result.column_count == 3
        assert "patient_id" in result.columns
        assert result.quality_score.total_score > 90.0


def test_analyze_remote_parquet_url(tmp_path):
    """Verify iragi.all.analyze dispatches remote Parquet files from cloud storage."""
    df = pd.DataFrame({
        "station_id": ["ST-A", "ST-B"],
        "co2_ppm": [415.2, 418.9],
        "status": ["ONLINE", "ONLINE"],
    })
    parquet_bytes_io = io.BytesIO()
    df.to_parquet(parquet_bytes_io)
    parquet_bytes = parquet_bytes_io.getvalue()

    mock_response = MagicMock()
    mock_response.read.side_effect = [parquet_bytes, b""]
    mock_response.headers = {}

    with patch("urllib.request.urlopen", return_value=mock_response):
        res = iragi.analyze("https://storage.googleapis.com/climate/co2_monitoring.parquet")
        assert res.file_type == "parquet"
        assert res.success is True
        assert res.overall_quality_score == 100.0
