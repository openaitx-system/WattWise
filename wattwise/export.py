"""Data export functionality for WattWise."""

import csv
import json
import os
from bisect import bisect_left
from datetime import datetime
from typing import Any


def export_history(
    history_file: str,
    output_file: str,
    fmt: str = "csv",
    start: str | None = None,
    end: str | None = None,
) -> int:
    """Export power/current history to CSV or JSON.

    Args:
        history_file: Path to the history.json file.
        output_file: Path to write the export.
        fmt: Output format, "csv" or "json".
        start: Optional ISO date string to filter from.
        end: Optional ISO date string to filter to.

    Returns:
        Number of records exported.

    Raises:
        FileNotFoundError: If history file doesn't exist.
        ValueError: If format is unsupported.
    """
    if not os.path.exists(history_file):
        raise FileNotFoundError(f"History file not found: {history_file}")

    with open(history_file, "r") as f:
        data = json.load(f)

    power_history: list[list[float]] = data.get("power", [])
    current_history: list[list[float]] = data.get("current", [])

    # Filter by date range
    if start:
        start_ts = datetime.fromisoformat(start).timestamp()
        power_history = [p for p in power_history if p[0] >= start_ts]
        current_history = [c for c in current_history if c[0] >= start_ts]

    if end:
        end_ts = datetime.fromisoformat(end).timestamp()
        power_history = [p for p in power_history if p[0] <= end_ts]
        current_history = [c for c in current_history if c[0] <= end_ts]

    # Build lookup for current readings by timestamp (tolerant matching)
    current_history_sorted = sorted(current_history, key=lambda item: item[0])
    current_times = [ts for ts, _ in current_history_sorted]
    current_tolerance_seconds = 2.0

    def _match_current(ts: float) -> float | None:
        if not current_times:
            return None
        pos = bisect_left(current_times, ts)
        candidate_indexes = []
        if pos < len(current_times):
            candidate_indexes.append(pos)
        if pos > 0:
            candidate_indexes.append(pos - 1)
        if not candidate_indexes:
            return None
        best_idx = min(
            candidate_indexes,
            key=lambda idx: abs(current_times[idx] - ts),
        )
        if abs(current_times[best_idx] - ts) <= current_tolerance_seconds:
            return float(current_history_sorted[best_idx][1])
        return None

    # Build export records
    records: list[dict[str, Any]] = []
    has_amperes = len(current_times) > 0

    for ts, watts in power_history:
        record: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(ts).isoformat(),
            "watts": round(watts, 2),
        }
        if has_amperes:
            amperes = _match_current(ts)
            record["amperes"] = round(amperes, 2) if amperes is not None else None
        records.append(record)

    if fmt == "json":
        with open(output_file, "w") as f:
            json.dump(records, f, indent=2)
    elif fmt == "csv":
        if not records:
            with open(output_file, "w") as f:
                f.write("")
            return 0
        fieldnames = ["timestamp", "watts"]
        if has_amperes:
            fieldnames.append("amperes")
        with open(output_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            if has_amperes:
                csv_records = []
                for record in records:
                    csv_record = record.copy()
                    if csv_record.get("amperes") is None:
                        csv_record["amperes"] = ""
                    csv_records.append(csv_record)
                writer.writerows(csv_records)
            else:
                writer.writerows(records)
    else:
        raise ValueError(f"Unsupported format: {fmt}. Use 'csv' or 'json'.")

    return len(records)
