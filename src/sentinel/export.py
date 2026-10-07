"""Export the sample datasets to CSV and JSON.

Writes every row (v1 + v2) of each registered dataset to `exports/<name>.csv`
and `exports/<name>.json`, so the data can be inspected, shared, or loaded into
a warehouse without running the demo. It also writes a drift manifest
`exports/<name>_drift.csv` / `.json` listing only the rows whose meaning
silently changed between v1 and v2 (the planted ground truth). Run with
`make export` or `python -m sentinel.export`.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .datasets import DATASETS, DatasetSpec

DRIFT_COLUMNS = ["row_id", "item", "column", "v1", "v2"]


def _columns(spec: DatasetSpec) -> list[str]:
    return ["row_id", "deployment_version", *spec.text_columns, "created_at"]


def drift_rows(spec: DatasetSpec) -> list[dict]:
    """Return one record per column that silently changed from v1 to v2.

    `item` is the row's identifying value (its first content column), so the
    manifest reads e.g. `iPhone 15 Pro | category | Mobile -> Home Appliances`.
    """
    rows = spec.rows()
    v1 = {r["row_id"]: r for r in rows if r["deployment_version"] == "v1"}
    v2 = {r["row_id"]: r for r in rows if r["deployment_version"] == "v2"}
    label_col = spec.text_columns[0]
    out: list[dict] = []
    for row_id, a in v1.items():
        b = v2.get(row_id)
        if b is None:
            continue
        for col in spec.text_columns:
            if a.get(col) != b.get(col):
                out.append({
                    "row_id": row_id,
                    "item": a.get(label_col),
                    "column": col,
                    "v1": a.get(col),
                    "v2": b.get(col),
                })
    return out


def export_dataset(spec: DatasetSpec, out_dir: Path) -> tuple[Path, Path]:
    """Write one dataset to <out_dir>/<name>.csv and <name>.json."""
    columns = _columns(spec)
    rows = spec.rows()

    csv_path = out_dir / f"{spec.name}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row[c] for c in columns})

    json_path = out_dir / f"{spec.name}.json"
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump([{c: row[c] for c in columns} for row in rows], fh, indent=2)
        fh.write("\n")

    return csv_path, json_path


def export_drift(spec: DatasetSpec, out_dir: Path) -> tuple[Path, Path]:
    """Write the drift manifest to <out_dir>/<name>_drift.csv and _drift.json."""
    records = drift_rows(spec)

    csv_path = out_dir / f"{spec.name}_drift.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=DRIFT_COLUMNS)
        writer.writeheader()
        writer.writerows(records)

    json_path = out_dir / f"{spec.name}_drift.json"
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2)
        fh.write("\n")

    return csv_path, json_path


def main() -> int:
    out_dir = Path("exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    for spec in DATASETS.values():
        export_dataset(spec, out_dir)
        export_drift(spec, out_dir)
        n = len(spec.rows())
        drifted = len(drift_rows(spec))
        print(f"{spec.name:8} {n:3} rows, {drifted:3} drifted "
              f"-> exports/{spec.name}.csv/.json + {spec.name}_drift.csv/.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
