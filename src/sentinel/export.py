"""Export the sample datasets to CSV and JSON.

Writes every row (v1 + v2) of each registered dataset to `exports/<name>.csv`
and `exports/<name>.json`, so the data can be inspected, shared, or loaded into
a warehouse without running the demo. Run with `make export` or
`python -m sentinel.export`.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .datasets import DATASETS, DatasetSpec


def _columns(spec: DatasetSpec) -> list[str]:
    return ["row_id", "deployment_version", *spec.text_columns, "created_at"]


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


def main() -> int:
    out_dir = Path("exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    for spec in DATASETS.values():
        csv_path, json_path = export_dataset(spec, out_dir)
        n = len(spec.rows())
        print(f"{spec.name:8} {n:3} rows -> {csv_path}, {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
