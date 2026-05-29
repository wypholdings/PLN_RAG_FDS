from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_fds.config import MANUFACTURERS, PROCESSED_DIR, REPORTS_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate RAG chunks.")
    parser.add_argument("--manufacturer", required=True)
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    args = parse_args()
    manufacturer = args.manufacturer
    if manufacturer not in MANUFACTURERS:
        raise SystemExit(f"Unknown manufacturer: {manufacturer}")

    slug = manufacturer.lower()
    metadata_dir = PROCESSED_DIR / "metadata" / manufacturer
    chunks_path = PROCESSED_DIR / "chunks" / f"{slug}_chunks.jsonl"
    chunks = load_jsonl(chunks_path)
    metadata_paths = sorted(path for path in metadata_dir.glob("sika__*.json"))
    if not metadata_paths:
        metadata_paths = sorted(path for path in metadata_dir.glob("*.json") if path.name != "duplicate_aliases.json")

    expected_sections = set()
    expected_tables = set()
    expected_images = set()
    for path in metadata_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        for section in data["sections"]:
            expected_sections.add((data["document_id"], section["number"]))
        expected_tables.update(table["table_id"] for table in data.get("tables", []))
        expected_images.update(image["image_id"] for image in data.get("images", []))

    covered_sections = {(chunk["document_id"], chunk["section_number"]) for chunk in chunks}
    covered_tables = {table_id for chunk in chunks for table_id in chunk.get("table_ids", [])}
    covered_images = {image_id for chunk in chunks for image_id in chunk.get("image_ids", [])}

    empty_chunks = [chunk["chunk_id"] for chunk in chunks if not chunk.get("content", "").strip()]
    missing_trace = [
        chunk["chunk_id"]
        for chunk in chunks
        if not chunk.get("trace") or not chunk.get("source_file") or not chunk.get("section_number")
    ]
    duplicate_chunk_ids = sorted(
        chunk_id
        for chunk_id in {chunk["chunk_id"] for chunk in chunks}
        if sum(1 for chunk in chunks if chunk["chunk_id"] == chunk_id) > 1
    )

    summary = {
        "manufacturer": manufacturer,
        "chunks": len(chunks),
        "expected_sections": len(expected_sections),
        "covered_sections": len(covered_sections),
        "missing_sections": sorted([f"{doc}:sec{sec}" for doc, sec in expected_sections - covered_sections]),
        "expected_tables": len(expected_tables),
        "covered_tables": len(covered_tables),
        "missing_tables": sorted(expected_tables - covered_tables),
        "expected_images": len(expected_images),
        "covered_images": len(covered_images),
        "missing_images": sorted(expected_images - covered_images),
        "empty_chunks": empty_chunks,
        "missing_trace": missing_trace,
        "duplicate_chunk_ids": duplicate_chunk_ids,
    }
    summary["status"] = (
        "pass"
        if not summary["missing_sections"]
        and not summary["missing_tables"]
        and not summary["missing_images"]
        and not empty_chunks
        and not missing_trace
        and not duplicate_chunk_ids
        else "review"
    )
    output_path = REPORTS_DIR / f"chunk_validation_{slug}.json"
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
