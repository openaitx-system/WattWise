"""Tests for wattwise.export module."""

import csv
import json
import os

import pytest  # type: ignore[import-not-found]

from wattwise.export import export_history


@pytest.fixture
def history_file(tmp_path):
    """Create a sample history file."""
    data = {
        "power": [
            [1700000000.0, 150.5],
            [1700000060.0, 200.3],
            [1700000120.0, 175.8],
        ],
        "current": [
            [1700000000.0, 0.65],
            [1700000060.0, 0.87],
            [1700000120.0, 0.76],
        ],
    }
    path = tmp_path / "history.json"
    with open(path, "w") as f:
        json.dump(data, f)
    return str(path)


class TestExportCSV:
    def test_export_csv_creates_file(self, history_file, tmp_path):
        output = str(tmp_path / "export.csv")
        count = export_history(history_file, output, fmt="csv")
        assert count == 3
        assert os.path.exists(output)

    def test_export_csv_has_header(self, history_file, tmp_path):
        output = str(tmp_path / "export.csv")
        export_history(history_file, output, fmt="csv")
        with open(output) as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames is not None
            assert "timestamp" in reader.fieldnames
            assert "watts" in reader.fieldnames
            assert "amperes" in reader.fieldnames

    def test_export_csv_row_count(self, history_file, tmp_path):
        output = str(tmp_path / "export.csv")
        export_history(history_file, output, fmt="csv")
        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 3

    def test_export_csv_matches_current_with_tolerance(self, tmp_path):
        data = {
            "power": [
                [1700000000.0, 100.0],
                [1700000060.0, 200.0],
            ],
            "current": [
                [1700000001.0, 0.55],
                [1700000061.0, 0.85],
            ],
        }
        history_path = tmp_path / "history.json"
        with open(history_path, "w") as f:
            json.dump(data, f)

        output = str(tmp_path / "export.csv")
        export_history(str(history_path), output, fmt="csv")

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert float(rows[0]["amperes"]) == pytest.approx(0.55, rel=1e-3)
        assert float(rows[1]["amperes"]) == pytest.approx(0.85, rel=1e-3)


class TestExportJSON:
    def test_export_json_creates_file(self, history_file, tmp_path):
        output = str(tmp_path / "export.json")
        count = export_history(history_file, output, fmt="json")
        assert count == 3
        assert os.path.exists(output)

    def test_export_json_structure(self, history_file, tmp_path):
        output = str(tmp_path / "export.json")
        export_history(history_file, output, fmt="json")
        with open(output) as f:
            records = json.load(f)
        assert len(records) == 3
        assert "timestamp" in records[0]
        assert "watts" in records[0]
        assert "amperes" in records[0]


class TestExportFilters:
    def test_filter_by_start(self, history_file, tmp_path):
        from datetime import datetime

        output = str(tmp_path / "export.csv")
        # Use a timestamp between record 1 and record 2 (local timezone safe)
        start_str = datetime.fromtimestamp(1700000030.0).isoformat()
        count = export_history(history_file, output, fmt="csv", start=start_str)
        assert count == 2

    def test_filter_by_end(self, history_file, tmp_path):
        from datetime import datetime

        output = str(tmp_path / "export.csv")
        # Use a timestamp between record 1 and record 2
        end_str = datetime.fromtimestamp(1700000030.0).isoformat()
        count = export_history(history_file, output, fmt="csv", end=end_str)
        assert count == 1


class TestExportErrors:
    def test_missing_history_file(self, tmp_path):
        output = str(tmp_path / "export.csv")
        with pytest.raises(FileNotFoundError):
            export_history("/nonexistent/history.json", output)

    def test_unsupported_format(self, history_file, tmp_path):
        output = str(tmp_path / "export.xml")
        with pytest.raises(ValueError, match="Unsupported format"):
            export_history(history_file, output, fmt="xml")
