from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_fds.config import MANUFACTURERS, PROCESSED_DIR, REPORTS_DIR
from rag_fds.pdf_utils import file_sha256, normalized_text_hash, read_pdf_text


REQUIRED_FRONT_MATTER_KEYS = {
    "document_id",
    "fabricante",
    "producto",
    "archivo_fuente",
    "paginas",
    "file_sha256",
    "text_sha256",
}

GENERIC_PRODUCT_NAMES = {
    "ficha de datos de seguridad",
    "hoja de datos de seguridad",
    "msds",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate converted Markdown/metadata outputs.")
    parser.add_argument("--manufacturer", required=True, help="Manufacturer to validate.")
    return parser.parse_args()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def front_matter_keys(markdown: str) -> set[str]:
    if not markdown.startswith("---\n"):
        return set()
    end = markdown.find("\n---", 4)
    if end == -1:
        return set()
    keys = set()
    for line in markdown[4:end].splitlines():
        if ":" in line:
            keys.add(line.split(":", 1)[0].strip())
    return keys


def validate_document(metadata_path: Path, manufacturer: str) -> dict:
    data = read_json(metadata_path)
    document_id = data["document_id"]
    markdown_path = PROCESSED_DIR / "markdown" / manufacturer / f"{document_id}.md"
    source_path = Path(data["source_path"])
    markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
    pdf_text = read_pdf_text(source_path)

    section_numbers = [section["number"] for section in data["sections"]]
    empty_sections = [
        str(section["number"])
        for section in data["sections"]
        if len((section.get("text") or "").strip()) < 40
    ]
    invalid_page_sections = [
        str(section["number"])
        for section in data["sections"]
        if section["page_start"] < 1
        or section["page_end"] < section["page_start"]
        or section["page_end"] > data["page_count"]
    ]

    headings = re.findall(r"(?m)^## Seccion\s+(\d+):", markdown)
    trace_notes = re.findall(r"(?m)^> Nota de trazabilidad: contenido extraido", markdown)
    table_trace_notes = re.findall(r"(?m)^> Nota de trazabilidad: tabla", markdown)
    image_trace_notes = re.findall(r"(?m)^> Nota de trazabilidad: imagen", markdown)
    keys = front_matter_keys(markdown)
    tables = data.get("tables", [])
    images = data.get("images", [])
    image_file_errors = []
    for image in images:
        image_path = PROCESSED_DIR / "markdown" / manufacturer / image["relative_markdown_path"]
        image_path = image_path.resolve()
        if not image_path.exists():
            image_file_errors.append(image["image_id"])
    table_errors = [
        table["table_id"]
        for table in tables
        if not table.get("markdown", "").strip() or "|---" not in table.get("markdown", "")
    ]
    image_metadata_errors = [
        image["image_id"]
        for image in images
        if not image.get("sha256") or not image.get("kind") or "Nota de trazabilidad" not in image.get("trace_note", "")
    ]

    checks = {
        "markdown_exists": markdown_path.exists(),
        "source_exists": source_path.exists(),
        "file_hash_matches": source_path.exists() and file_sha256(source_path) == data["file_sha256"],
        "text_hash_matches": normalized_text_hash(pdf_text.full_text) == data["text_sha256"],
        "page_count_matches": pdf_text.page_count == data["page_count"],
        "product_name_is_specific": data["product"].strip().casefold() not in GENERIC_PRODUCT_NAMES,
        "has_required_front_matter": REQUIRED_FRONT_MATTER_KEYS.issubset(keys),
        "section_count_is_16": data["section_count"] == 16 and len(data["sections"]) == 16,
        "sections_are_1_to_16": section_numbers == list(range(1, 17)),
        "markdown_has_16_section_headings": [int(value) for value in headings] == list(range(1, 17)),
        "markdown_has_trace_note_per_section": len(trace_notes) == 16,
        "tables_have_markdown": not table_errors,
        "markdown_has_trace_note_per_table": len(table_trace_notes) == len(tables),
        "images_have_files": not image_file_errors,
        "images_have_metadata": not image_metadata_errors,
        "markdown_has_trace_note_per_image": len(image_trace_notes) == len(images),
        "images_have_ocr_field": all("ocr_text" in image for image in images),
        "no_empty_sections": not empty_sections,
        "valid_page_ranges": not invalid_page_sections,
        "no_extraction_errors": not data["extraction_errors"],
        "no_conversion_warnings": not data["warnings"],
    }
    failed_checks = [name for name, passed in checks.items() if not passed]
    quality_score = round(100 * (len(checks) - len(failed_checks)) / len(checks), 2)

    return {
        "manufacturer": manufacturer,
        "document_id": document_id,
        "source_file": data["source_file"],
        "product": data["product"],
        "quality_score": quality_score,
        "status": "pass" if not failed_checks else "review",
        "failed_checks": "|".join(failed_checks),
        "section_count": data["section_count"],
        "page_count": data["page_count"],
        "markdown_chars": len(markdown),
        "table_count": len(tables),
        "image_count": len(images),
        "empty_sections": ",".join(empty_sections),
        "invalid_page_sections": ",".join(invalid_page_sections),
        "table_errors": ",".join(table_errors),
        "image_file_errors": ",".join(image_file_errors),
        "image_metadata_errors": ",".join(image_metadata_errors),
        "warnings": "|".join(data["warnings"]),
        "extraction_errors": "|".join(data["extraction_errors"]),
        "markdown_path": str(markdown_path),
        "metadata_path": str(metadata_path),
    }


def validate_aliases(manufacturer: str) -> tuple[list[dict], list[str]]:
    aliases_path = PROCESSED_DIR / "metadata" / manufacturer / "duplicate_aliases.json"
    if not aliases_path.exists():
        return [], []
    aliases = json.loads(aliases_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for alias in aliases:
        canonical_metadata = PROCESSED_DIR / "metadata" / manufacturer / f"{alias['canonical_document_id']}.json"
        if not canonical_metadata.exists():
            errors.append(f"missing_canonical_metadata:{alias['canonical_document_id']}")
            continue
        canonical = read_json(canonical_metadata)
        if canonical["text_sha256"] != alias["text_sha256"]:
            errors.append(f"text_hash_mismatch:{alias['alias_document_id']}")
    return aliases, errors


def validate_asset_inventory(manufacturer: str, metadata_paths: list[Path]) -> list[str]:
    referenced: set[Path] = set()
    markdown_dir = PROCESSED_DIR / "markdown" / manufacturer
    for metadata_path in metadata_paths:
        data = read_json(metadata_path)
        for image in data.get("images", []):
            referenced.add((markdown_dir / image["relative_markdown_path"]).resolve())

    assets_dir = PROCESSED_DIR / "assets" / manufacturer
    actual = {
        path.resolve()
        for path in assets_dir.rglob("*")
        if path.is_file() and path.name != ".DS_Store"
    }
    errors = []
    for path in sorted(actual - referenced):
        errors.append(f"orphan_asset:{path}")
    for path in sorted(referenced - actual):
        errors.append(f"missing_asset:{path}")
    return errors


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
    metadata_paths = sorted(path for path in metadata_dir.glob("*.json") if path.name != "duplicate_aliases.json")
    if not metadata_paths:
        raise SystemExit(f"No metadata files found in {metadata_dir}")

    rows = [validate_document(path, manufacturer) for path in metadata_paths]
    aliases, alias_errors = validate_aliases(manufacturer)
    asset_errors = validate_asset_inventory(manufacturer, metadata_paths)

    report_csv = REPORTS_DIR / f"quality_report_{manufacturer.lower()}.csv"
    report_json = REPORTS_DIR / f"quality_summary_{manufacturer.lower()}.json"
    write_csv(rows, report_csv)

    summary = {
        "manufacturer": manufacturer,
        "documents_validated": len(rows),
        "documents_passed": sum(1 for row in rows if row["status"] == "pass"),
        "documents_for_review": sum(1 for row in rows if row["status"] != "pass"),
        "average_quality_score": round(sum(row["quality_score"] for row in rows) / len(rows), 2),
        "duplicate_aliases": len(aliases),
        "alias_errors": alias_errors,
        "asset_errors": asset_errors,
        "report_csv": str(report_csv),
    }
    report_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["documents_for_review"] or alias_errors or asset_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
