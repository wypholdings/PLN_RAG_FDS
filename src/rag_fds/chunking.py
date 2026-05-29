from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    manufacturer: str
    product: str
    source_file: str
    section_number: int
    section_title: str
    page_start: int
    page_end: int
    chunk_index: int
    chunk_count_for_section: int
    content: str
    content_types: list[str]
    table_ids: list[str]
    image_ids: list[str]
    asset_paths: list[str]
    trace: dict


def estimate_tokens(text: str) -> int:
    # Approximation good enough for stable chunk sizing without model-specific tokenizers.
    return max(1, len(re.findall(r"\S+", text)))


def split_paragraphs(text: str) -> list[str]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text.strip()) if item.strip()]
    if paragraphs:
        return paragraphs
    return [text.strip()] if text.strip() else []


def split_text(text: str, max_tokens: int = 850, overlap_tokens: int = 100) -> list[str]:
    paragraphs = split_paragraphs(text)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for paragraph in paragraphs:
        paragraph_tokens = estimate_tokens(paragraph)
        if paragraph_tokens > max_tokens:
            if current:
                chunks.append("\n\n".join(current).strip())
                current = []
                current_tokens = 0
            chunks.extend(split_long_paragraph(paragraph, max_tokens, overlap_tokens))
            continue
        if current and current_tokens + paragraph_tokens > max_tokens:
            chunks.append("\n\n".join(current).strip())
            overlap = tail_words(chunks[-1], overlap_tokens)
            current = [overlap, paragraph] if overlap else [paragraph]
            current_tokens = estimate_tokens("\n\n".join(current))
        else:
            current.append(paragraph)
            current_tokens += paragraph_tokens

    if current:
        chunks.append("\n\n".join(current).strip())
    return [chunk for chunk in chunks if chunk.strip()]


def split_long_paragraph(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    words = re.findall(r"\S+", text)
    chunks = []
    step = max(1, max_tokens - overlap_tokens)
    for start in range(0, len(words), step):
        piece = " ".join(words[start : start + max_tokens]).strip()
        if piece:
            chunks.append(piece)
        if start + max_tokens >= len(words):
            break
    return chunks


def tail_words(text: str, count: int) -> str:
    words = re.findall(r"\S+", text)
    if len(words) <= count:
        return " ".join(words)
    return " ".join(words[-count:])


def section_related_tables(metadata: dict, section_number: int) -> list[dict]:
    return [table for table in metadata.get("tables", []) if table["section_number"] == section_number]


def section_related_images(metadata: dict, section_number: int) -> list[dict]:
    return [image for image in metadata.get("images", []) if image["section_number"] == section_number]


def build_section_content(section: dict, tables: list[dict], images: list[dict]) -> tuple[str, list[str]]:
    parts = [
        f"Documento: {section.get('source_file', '')}".strip(),
        f"Seccion {section['number']}: {section['title']}",
        "",
        section.get("text", "").strip(),
    ]
    content_types = ["text"]

    for table in tables:
        parts.extend(
            [
                "",
                f"[Tabla {table['table_id']}]",
                table["markdown"],
                table["trace_note"],
            ]
        )
        content_types.append("table")

    for image in images:
        ocr_text = image.get("ocr_text", "").strip() or "OCR sin texto legible."
        parts.extend(
            [
                "",
                f"[Imagen {image['image_id']}]",
                f"Tipo: {image['kind']}. Archivo: {image['relative_markdown_path']}.",
                image["trace_note"],
                "Texto OCR:",
                ocr_text,
            ]
        )
        content_types.append("image")
        content_types.append("ocr")

    return "\n".join(part for part in parts if part is not None).strip(), sorted(set(content_types))


def chunks_from_metadata(metadata: dict, max_tokens: int = 850, overlap_tokens: int = 100) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in metadata["sections"]:
        section = {**section, "source_file": metadata["source_file"]}
        tables = section_related_tables(metadata, section["number"])
        images = section_related_images(metadata, section["number"])
        section_content, content_types = build_section_content(section, tables, images)
        content_pieces = split_text(section_content, max_tokens=max_tokens, overlap_tokens=overlap_tokens)
        chunk_count = len(content_pieces)
        table_ids = [table["table_id"] for table in tables]
        image_ids = [image["image_id"] for image in images]
        asset_paths = [image["relative_markdown_path"] for image in images]

        for index, content in enumerate(content_pieces, start=1):
            chunk_id = f"{metadata['document_id']}__sec{section['number']:02d}__chunk{index:02d}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_id=metadata["document_id"],
                    manufacturer=metadata["manufacturer"],
                    product=metadata["product"],
                    source_file=metadata["source_file"],
                    section_number=section["number"],
                    section_title=section["title"],
                    page_start=section["page_start"],
                    page_end=section["page_end"],
                    chunk_index=index,
                    chunk_count_for_section=chunk_count,
                    content=content,
                    content_types=content_types,
                    table_ids=table_ids,
                    image_ids=image_ids,
                    asset_paths=asset_paths,
                    trace={
                        "source_file": metadata["source_file"],
                        "section": section["number"],
                        "section_title": section["title"],
                        "pages": [section["page_start"], section["page_end"]],
                        "tables": table_ids,
                        "images": image_ids,
                    },
                )
            )
    return chunks


def load_metadata_files(metadata_dir: Path) -> list[dict]:
    items = []
    for path in sorted(metadata_dir.glob("*.json")):
        if path.name == "duplicate_aliases.json":
            continue
        items.append(json.loads(path.read_text(encoding="utf-8")))
    return items


def write_jsonl(chunks: list[Chunk], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")


def chunk_to_row(chunk: Chunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "manufacturer": chunk.manufacturer,
        "product": chunk.product,
        "source_file": chunk.source_file,
        "section_number": chunk.section_number,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "chunk_index": chunk.chunk_index,
        "chunk_count_for_section": chunk.chunk_count_for_section,
        "token_estimate": estimate_tokens(chunk.content),
        "content_types": ",".join(chunk.content_types),
        "table_count": len(chunk.table_ids),
        "image_count": len(chunk.image_ids),
        "content_chars": len(chunk.content),
    }
