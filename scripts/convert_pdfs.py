from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_fds.config import MANUFACTURERS, PROCESSED_DIR, REPORTS_DIR
from rag_fds.markdown_converter import convert_pdf, write_converted_document


PILOT_FILES = {
    "SIKA": [
        "FDS 27 - Epoxi_100HS_S300_CA.pdf",
        "FDS 20 - Esmalte Alquídico Serie 31.pdf",
        "FDS 69 - Esmalte Uretano Part A - SIKA.pdf",
    ],
    "Pintuco": [
        "FDS 41 - PINTURA ACRILICA CONSTRUCCION ALTA ASEPSIA BLANCO 27580 - PINTUCO .pdf",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert FDS PDFs to Markdown.")
    parser.add_argument("--manufacturer", required=True, help="Manufacturer folder name.")
    parser.add_argument("--pilot", action="store_true", help="Convert the configured pilot files.")
    parser.add_argument("--all", action="store_true", help="Convert all PDFs for the manufacturer.")
    parser.add_argument(
        "--include-duplicates",
        action="store_true",
        help="Convert duplicate documents instead of recording them as aliases.",
    )
    parser.add_argument("--files", nargs="*", default=[], help="Specific PDF file names to convert.")
    return parser.parse_args()


def canonical_sort_key(path: Path) -> tuple[int, str]:
    name = path.name.casefold()
    return (0 if name.startswith("fds") else 1, name)


def resolve_files(manufacturer: str, pilot: bool, all_files: bool, file_names: list[str]) -> list[Path]:
    source_dir = MANUFACTURERS.get(manufacturer)
    if source_dir is None:
        raise SystemExit(f"Unknown manufacturer: {manufacturer}")
    if all_files:
        return sorted(source_dir.glob("*.pdf"), key=canonical_sort_key)
    if pilot:
        file_names = PILOT_FILES.get(manufacturer, [])
    if not file_names:
        raise SystemExit("Use --pilot, --all, or --files.")
    paths = [source_dir / file_name for file_name in file_names]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise SystemExit("Missing files:\n" + "\n".join(missing))
    return paths


def write_report(rows: list[dict], manufacturer: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"conversion_report_{manufacturer.lower()}.csv"
    with report_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return report_path


def write_aliases(aliases: list[dict], manufacturer: str) -> Path:
    metadata_dir = PROCESSED_DIR / "metadata" / manufacturer
    metadata_dir.mkdir(parents=True, exist_ok=True)
    aliases_path = metadata_dir / "duplicate_aliases.json"
    aliases_path.write_text(json.dumps(aliases, ensure_ascii=False, indent=2), encoding="utf-8")
    return aliases_path


def main() -> int:
    args = parse_args()
    paths = resolve_files(args.manufacturer, args.pilot, args.all, args.files)
    rows: list[dict] = []
    aliases: list[dict] = []
    seen_text_hashes: dict[str, dict] = {}

    for path in paths:
        document = convert_pdf(path, args.manufacturer, PROCESSED_DIR / "assets")
        canonical = seen_text_hashes.get(document.text_sha256)
        if canonical and not args.include_duplicates:
            aliases.append(
                {
                    "alias_source_file": document.source_file,
                    "alias_document_id": document.document_id,
                    "canonical_source_file": canonical["source_file"],
                    "canonical_document_id": canonical["document_id"],
                    "text_sha256": document.text_sha256,
                }
            )
            rows.append(
                {
                    "status": "duplicate_skipped",
                    "manufacturer": document.manufacturer,
                    "document_id": document.document_id,
                    "source_file": document.source_file,
                    "product": document.product,
                    "page_count": document.page_count,
                    "section_count": len(document.sections),
                    "table_count": len(document.tables),
                    "image_count": len(document.images),
                    "warnings": "duplicate_of: " + canonical["document_id"],
                    "extraction_errors": " | ".join(document.extraction_errors),
                    "markdown_path": "",
                    "metadata_path": "",
                    "canonical_document_id": canonical["document_id"],
                }
            )
            print(f"Skipped duplicate {document.source_file} -> {canonical['source_file']}")
            continue

        markdown_path, metadata_path = write_converted_document(document, PROCESSED_DIR)
        seen_text_hashes[document.text_sha256] = {
            "document_id": document.document_id,
            "source_file": document.source_file,
        }
        rows.append(
            {
                "status": "converted",
                "manufacturer": document.manufacturer,
                "document_id": document.document_id,
                "source_file": document.source_file,
                "product": document.product,
                "page_count": document.page_count,
                "section_count": len(document.sections),
                "table_count": len(document.tables),
                "image_count": len(document.images),
                "warnings": " | ".join(document.warnings),
                "extraction_errors": " | ".join(document.extraction_errors),
                "markdown_path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "canonical_document_id": document.document_id,
            }
        )
        print(f"Converted {document.source_file} -> {markdown_path}")

    report_path = write_report(rows, args.manufacturer)
    aliases_path = write_aliases(aliases, args.manufacturer)
    print(f"Conversion report written to: {report_path}")
    print(f"Duplicate aliases written to: {aliases_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
