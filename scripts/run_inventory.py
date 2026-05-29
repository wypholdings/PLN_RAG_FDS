from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_fds.config import MANUFACTURERS, REPORTS_DIR
from rag_fds.inventory import (
    add_duplicate_flags,
    inventory_manufacturer,
    summarize_inventory,
    write_csv,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PDF inventory reports.")
    parser.add_argument(
        "--manufacturers",
        nargs="+",
        default=["SIKA", "Pintuco"],
        help="Manufacturer folders to inventory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = []
    for manufacturer in args.manufacturers:
        source_dir = MANUFACTURERS.get(manufacturer)
        if source_dir is None:
            raise SystemExit(f"Unknown manufacturer: {manufacturer}")
        if not source_dir.exists():
            raise SystemExit(f"Missing source directory: {source_dir}")
        rows.extend(inventory_manufacturer(manufacturer, source_dir))

    add_duplicate_flags(rows, "file_sha256", "duplicate_file_group")
    add_duplicate_flags(rows, "text_sha256", "duplicate_text_group")

    write_csv(rows, REPORTS_DIR / "inventory.csv")
    write_json(rows, REPORTS_DIR / "inventory.json")
    summary = summarize_inventory(rows)
    write_json(summary, REPORTS_DIR / "inventory_summary.json")

    print(f"Inventoried {len(rows)} PDF files.")
    for manufacturer, values in summary["manufacturers"].items():
        print(
            f"- {manufacturer}: {values['documents']} docs, {values['pages']} pages, "
            f"{values['documents_with_16_sections']} with 16 sections, "
            f"{values['duplicate_text_groups']} duplicate text groups"
        )
    print(f"Reports written to: {REPORTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
