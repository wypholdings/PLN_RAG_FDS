from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_fds.chunking import chunk_to_row, chunks_from_metadata, load_metadata_files, write_jsonl
from rag_fds.config import MANUFACTURERS, PROCESSED_DIR, REPORTS_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RAG chunks from converted metadata.")
    parser.add_argument("--manufacturer", required=True)
    parser.add_argument("--max-tokens", type=int, default=850)
    parser.add_argument("--overlap-tokens", type=int, default=100)
    return parser.parse_args()


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    manufacturer = args.manufacturer
    if manufacturer not in MANUFACTURERS:
        raise SystemExit(f"Unknown manufacturer: {manufacturer}")

    metadata_dir = PROCESSED_DIR / "metadata" / manufacturer
    metadata_items = load_metadata_files(metadata_dir)
    chunks = []
    for metadata in metadata_items:
        chunks.extend(
            chunks_from_metadata(
                metadata,
                max_tokens=args.max_tokens,
                overlap_tokens=args.overlap_tokens,
            )
        )

    manufacturer_slug = manufacturer.lower()
    chunks_path = PROCESSED_DIR / "chunks" / f"{manufacturer_slug}_chunks.jsonl"
    report_path = REPORTS_DIR / f"chunk_report_{manufacturer_slug}.csv"
    summary_path = REPORTS_DIR / f"chunk_summary_{manufacturer_slug}.json"
    rows = [chunk_to_row(chunk) for chunk in chunks]
    write_jsonl(chunks, chunks_path)
    write_csv(rows, report_path)

    content_type_counter = Counter()
    for chunk in chunks:
        content_type_counter.update(chunk.content_types)
    expected_sections = {
        (metadata["document_id"], section["number"])
        for metadata in metadata_items
        for section in metadata["sections"]
    }
    summary = {
        "manufacturer": manufacturer,
        "documents": len(metadata_items),
        "chunks": len(chunks),
        "sections_expected": len(expected_sections),
        "full_fds_sections_expected": len(metadata_items) * 16,
        "sections_covered": len({(chunk.document_id, chunk.section_number) for chunk in chunks}),
        "chunks_path": str(chunks_path),
        "report_path": str(report_path),
        "content_type_counts": dict(sorted(content_type_counter.items())),
        "max_tokens": args.max_tokens,
        "overlap_tokens": args.overlap_tokens,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
