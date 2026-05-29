from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from .pdf_utils import file_sha256, guess_product_name, normalized_text_hash, read_pdf_text
from .sections import detect_sections, missing_sections


def inventory_manufacturer(manufacturer: str, source_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(source_dir.glob("*.pdf")):
        pdf_text = read_pdf_text(path)
        sections = detect_sections(pdf_text.page_texts)
        rows.append(
            {
                "manufacturer": manufacturer,
                "file_name": path.name,
                "relative_path": str(path),
                "file_sha256": file_sha256(path),
                "text_sha256": normalized_text_hash(pdf_text.full_text),
                "page_count": pdf_text.page_count,
                "pages_with_text": pdf_text.pages_with_text,
                "text_chars": pdf_text.text_chars,
                "product_guess": guess_product_name(pdf_text.full_text, path.stem),
                "sections_found": len(sections),
                "sections_found_numbers": ",".join(str(hit.number) for hit in sections),
                "sections_missing": ",".join(str(number) for number in missing_sections(sections)),
                "first_section_page": sections[0].page if sections else "",
                "extraction_error_count": len(pdf_text.extraction_errors),
                "extraction_errors": " | ".join(pdf_text.extraction_errors),
            }
        )
    return rows


def add_duplicate_flags(rows: list[dict], key: str, output_key: str) -> None:
    groups: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        groups[row[key]].append(index)
    group_number = 1
    for indexes in groups.values():
        if len(indexes) < 2:
            for index in indexes:
                rows[index][output_key] = ""
            continue
        label = f"dup-{group_number:02d}"
        group_number += 1
        for index in indexes:
            rows[index][output_key] = label


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(data: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def summarize_inventory(rows: list[dict]) -> dict:
    by_manufacturer: dict[str, dict] = {}
    for row in rows:
        item = by_manufacturer.setdefault(
            row["manufacturer"],
            {
                "documents": 0,
                "pages": 0,
                "documents_with_16_sections": 0,
                "documents_with_extraction_errors": 0,
                "duplicate_file_groups": set(),
                "duplicate_text_groups": set(),
                "low_text_documents": 0,
            },
        )
        item["documents"] += 1
        item["pages"] += int(row["page_count"] or 0)
        item["documents_with_16_sections"] += int(row["sections_found"] == 16)
        item["documents_with_extraction_errors"] += int(row["extraction_error_count"] > 0)
        item["low_text_documents"] += int(row["text_chars"] < 1000)
        if row["duplicate_file_group"]:
            item["duplicate_file_groups"].add(row["duplicate_file_group"])
        if row["duplicate_text_group"]:
            item["duplicate_text_groups"].add(row["duplicate_text_group"])
    for item in by_manufacturer.values():
        item["duplicate_file_groups"] = len(item["duplicate_file_groups"])
        item["duplicate_text_groups"] = len(item["duplicate_text_groups"])
    return {"manufacturers": by_manufacturer}
