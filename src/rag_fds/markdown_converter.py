from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

from .pdf_utils import file_sha256, guess_product_name, normalized_text_hash, read_pdf_text
from .sections import SECTION_PATTERN, SECTION_TITLES, SectionHit, iter_section_hits, missing_sections
from .structured_extraction import (
    ExtractedImage,
    ExtractedTable,
    dataclass_list,
    extract_images,
    extract_tables,
    group_by_section,
)


@dataclass(frozen=True)
class SectionBlock:
    number: int
    title: str
    page_start: int
    page_end: int
    text: str


@dataclass(frozen=True)
class ConvertedDocument:
    document_id: str
    manufacturer: str
    source_path: str
    source_file: str
    product: str
    page_count: int
    file_sha256: str
    text_sha256: str
    sections: list[SectionBlock]
    tables: list[ExtractedTable]
    images: list[ExtractedImage]
    warnings: list[str]
    extraction_errors: list[str]


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = value.replace("ñ", "n")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "documento"


def yaml_quote(value: object) -> str:
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def first_hits_by_section(hits: list[SectionHit]) -> list[SectionHit]:
    selected: dict[int, SectionHit] = {}
    grouped: dict[int, list[SectionHit]] = {}
    for hit in sorted(hits, key=lambda item: (item.page, item.start)):
        grouped.setdefault(hit.number, []).append(hit)

    for number, section_hits in grouped.items():
        selected[number] = select_best_section_hit(number, section_hits)
    return sorted(selected.values(), key=lambda item: (item.page, item.start))


def normalize_heading(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def heading_match_score(number: int, title: str) -> int:
    expected = normalize_heading(SECTION_TITLES[number])
    candidate = normalize_heading(title)
    if not candidate:
        return 0
    if candidate.startswith(expected) or expected.startswith(candidate):
        return 100
    if expected in candidate:
        return 60

    expected_terms = [term for term in expected.split() if len(term) > 3]
    return sum(1 for term in expected_terms if term in candidate)


def select_best_section_hit(number: int, hits: list[SectionHit]) -> SectionHit:
    earliest = sorted(hits, key=lambda item: (item.page, item.start))[0]
    scored = [
        (heading_match_score(number, hit.title), hit.page, hit.start, hit)
        for hit in hits
    ]
    best_score = max(score for score, _, _, _ in scored)
    if best_score <= 0:
        return earliest
    matching_hits = [item for item in scored if item[0] == best_score]
    return sorted(matching_hits, key=lambda item: (item[1], item[2]))[0][3]


def section_text_from_pages(page_texts: list[str], start: SectionHit, end: SectionHit | None) -> str:
    chunks: list[str] = []
    for page_number in range(start.page, (end.page if end else len(page_texts)) + 1):
        page_text = page_texts[page_number - 1] or ""
        start_offset = start.start if page_number == start.page else 0
        if end and page_number == end.page:
            end_offset = end.start
        else:
            end_offset = len(page_text)
        if start_offset < end_offset:
            chunks.append(page_text[start_offset:end_offset])
    return "\n".join(chunks)


def strip_section_heading(text: str) -> str:
    normalized = text.lstrip()
    match = SECTION_PATTERN.match(normalized)
    if match:
        normalized = normalized[match.end() :]
    return normalized.strip()


def normalize_markdown_text(text: str, product: str | None = None) -> str:
    lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = " ".join(raw_line.rstrip().split())
        if is_running_header_or_footer(line, product):
            continue
        if line in {"", " "}:
            lines.append("")
            continue
        line = re.sub(r"^[•●▪▫]\s*", "- ", line)
        line = re.sub(r"^\(?([a-z])\)\s+", r"- (\1) ", line)
        lines.append(line)

    compact: list[str] = []
    blank_count = 0
    for line in lines:
        if not line:
            blank_count += 1
            if blank_count <= 1:
                compact.append("")
            continue
        blank_count = 0
        compact.append(line)
    return "\n".join(compact).strip()


def is_running_header_or_footer(line: str, product: str | None = None) -> bool:
    if not line:
        return False
    if product and line.casefold() == product.casefold():
        return True
    if re.search(r"fecha de emisi[oó]n:.*msds no\.", line, flags=re.IGNORECASE):
        return True
    if re.fullmatch(r"\d+\s*/\s*\d+", line):
        return True
    return False


def build_section_blocks(page_texts: list[str], product: str | None = None) -> tuple[list[SectionBlock], list[str]]:
    warnings: list[str] = []
    hits = first_hits_by_section(iter_section_hits(page_texts))
    missing = missing_sections(hits)
    if missing:
        warnings.append("missing_sections: " + ",".join(str(number) for number in missing))
    section_numbers = [hit.number for hit in hits]
    if section_numbers != sorted(section_numbers):
        warnings.append("section_order_not_ascending: " + ",".join(str(number) for number in section_numbers))

    sections: list[SectionBlock] = []
    for index, hit in enumerate(hits):
        next_hit = hits[index + 1] if index + 1 < len(hits) else None
        raw_text = section_text_from_pages(page_texts, hit, next_hit)
        clean_text = normalize_markdown_text(strip_section_heading(raw_text), product)
        sections.append(
            SectionBlock(
                number=hit.number,
                title=SECTION_TITLES.get(hit.number, hit.title),
                page_start=hit.page,
                page_end=(next_hit.page if next_hit else len(page_texts)),
                text=clean_text,
            )
        )
    return sections, warnings


def section_ranges(sections: list[SectionBlock]) -> dict[int, tuple[int, int]]:
    return {section.number: (section.page_start, section.page_end) for section in sections}


def convert_pdf(path: Path, manufacturer: str, assets_root: Path | None = None) -> ConvertedDocument:
    pdf_text = read_pdf_text(path)
    product = guess_product_name(pdf_text.full_text, path.stem)
    document_id = f"{slugify(manufacturer)}__{slugify(path.stem)}"
    sections, warnings = build_section_blocks(pdf_text.page_texts, product)
    ranges = section_ranges(sections)
    tables = extract_tables(path, document_id, ranges)
    images: list[ExtractedImage] = []
    if assets_root is not None:
        images = extract_images(path, document_id, manufacturer, ranges, assets_root)

    low_text_pages = [
        str(index)
        for index, page_text in enumerate(pdf_text.page_texts, start=1)
        if len(page_text.strip()) < 80
    ]
    if low_text_pages:
        warnings.append("low_text_pages: " + ",".join(low_text_pages))
    if len(sections) != 16:
        warnings.append(f"section_count: {len(sections)}")

    return ConvertedDocument(
        document_id=document_id,
        manufacturer=manufacturer,
        source_path=str(path),
        source_file=path.name,
        product=product,
        page_count=pdf_text.page_count,
        file_sha256=file_sha256(path),
        text_sha256=normalized_text_hash(pdf_text.full_text),
        sections=sections,
        tables=tables,
        images=images,
        warnings=warnings,
        extraction_errors=pdf_text.extraction_errors,
    )


def document_to_markdown(document: ConvertedDocument) -> str:
    tables_by_section = group_by_section(document.tables)
    images_by_section = group_by_section(document.images)
    lines = [
        "---",
        f"document_id: {yaml_quote(document.document_id)}",
        f"fabricante: {yaml_quote(document.manufacturer)}",
        f"producto: {yaml_quote(document.product)}",
        f"archivo_fuente: {yaml_quote(document.source_file)}",
        f"paginas: {document.page_count}",
        f"file_sha256: {yaml_quote(document.file_sha256)}",
        f"text_sha256: {yaml_quote(document.text_sha256)}",
        "---",
        "",
        f"# Ficha de Datos de Seguridad - {document.product}",
        "",
        "## Metadatos",
        "",
        f"- Fabricante: {document.manufacturer}",
        f"- Archivo fuente: `{document.source_file}`",
        f"- Paginas: {document.page_count}",
        f"- Secciones detectadas: {len(document.sections)} de 16",
        f"- Tablas extraidas: {len(document.tables)}",
        f"- Imagenes extraidas: {len(document.images)}",
        "",
        "## Tabla de secciones detectadas",
        "",
        "| Seccion | Titulo normalizado | Paginas |",
        "|---:|---|---:|",
    ]
    for section in document.sections:
        pages = (
            str(section.page_start)
            if section.page_start == section.page_end
            else f"{section.page_start}-{section.page_end}"
        )
        lines.append(f"| {section.number} | {section.title} | {pages} |")

    for section in document.sections:
        lines.extend(
            [
                "",
                f"## Seccion {section.number}: {section.title}",
                "",
                f"> Nota de trazabilidad: contenido extraido de la pagina {section.page_start}"
                + (f" a la pagina {section.page_end}" if section.page_end != section.page_start else "")
                + f" del PDF fuente `{document.source_file}`.",
                "",
                section.text or "_Sin texto extraido en esta seccion._",
            ]
        )
        section_tables = tables_by_section.get(section.number, [])
        if section_tables:
            lines.extend(["", "### Tablas extraidas de esta seccion", ""])
            for table in section_tables:
                lines.extend(
                    [
                        f"#### Tabla `{table.table_id}`",
                        "",
                        table.markdown,
                        "",
                        f"> {table.trace_note}",
                        "",
                    ]
                )

        section_images = images_by_section.get(section.number, [])
        if section_images:
            lines.extend(["", "### Imagenes extraidas de esta seccion", ""])
            for image in section_images:
                ocr_text = image.ocr_text if image.ocr_text else "OCR sin texto legible."
                lines.extend(
                    [
                        f"#### Imagen `{image.image_id}`",
                        "",
                        f"![{image.kind} pagina {image.page}]({image.relative_markdown_path})",
                        "",
                        f"> {image.trace_note}",
                        "",
                        "**Texto OCR de la imagen:**",
                        "",
                        "```text",
                        ocr_text,
                        "```",
                        "",
                    ]
                )

    if document.warnings or document.extraction_errors:
        lines.extend(["", "## Alertas de extraccion", ""])
        for warning in document.warnings:
            lines.append(f"- {warning}")
        for error in document.extraction_errors:
            lines.append(f"- {error}")

    return "\n".join(lines).rstrip() + "\n"


def document_to_metadata(document: ConvertedDocument) -> dict:
    return {
        "document_id": document.document_id,
        "manufacturer": document.manufacturer,
        "source_path": document.source_path,
        "source_file": document.source_file,
        "product": document.product,
        "page_count": document.page_count,
        "file_sha256": document.file_sha256,
        "text_sha256": document.text_sha256,
        "section_count": len(document.sections),
        "sections": [asdict(section) for section in document.sections],
        "tables": dataclass_list(document.tables),
        "images": dataclass_list(document.images),
        "warnings": document.warnings,
        "extraction_errors": document.extraction_errors,
    }


def write_converted_document(document: ConvertedDocument, output_root: Path) -> tuple[Path, Path]:
    markdown_dir = output_root / "markdown" / document.manufacturer
    metadata_dir = output_root / "metadata" / document.manufacturer
    markdown_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = markdown_dir / f"{document.document_id}.md"
    metadata_path = metadata_dir / f"{document.document_id}.json"
    markdown_path.write_text(document_to_markdown(document), encoding="utf-8")
    metadata_path.write_text(
        json.dumps(document_to_metadata(document), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return markdown_path, metadata_path
