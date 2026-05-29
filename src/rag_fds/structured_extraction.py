from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

from .sections import SECTION_PATTERN, normalize_text


@dataclass(frozen=True)
class SectionAnchor:
    number: int
    page: int
    y0: float


@dataclass(frozen=True)
class ExtractedImage:
    image_id: str
    page: int
    section_number: int
    file_name: str
    relative_markdown_path: str
    width: int
    height: int
    bbox: tuple[float, float, float, float]
    sha256: str
    kind: str
    ocr_text: str
    trace_note: str


@dataclass(frozen=True)
class ExtractedTable:
    table_id: str
    page: int
    section_number: int
    bbox: tuple[float, float, float, float]
    markdown: str
    trace_note: str


def detect_section_anchors(pdf_path: Path) -> list[SectionAnchor]:
    anchors: list[SectionAnchor] = []
    with fitz.open(pdf_path) as document:
        for page_index, page in enumerate(document, start=1):
            data = page.get_text("dict")
            for block in data.get("blocks", []):
                for line in block.get("lines", []):
                    text = " ".join(span.get("text", "") for span in line.get("spans", [])).strip()
                    normalized = normalize_text(text)
                    match = SECTION_PATTERN.search(normalized)
                    if not match:
                        continue
                    title = " ".join((match.group(2) or "").split())
                    if sum(character.isalpha() for character in title) < 3:
                        continue
                    anchors.append(
                        SectionAnchor(
                            number=int(match.group(1)),
                            page=page_index,
                            y0=float(line["bbox"][1]),
                        )
                    )
    return anchors


def section_for_bbox(
    page: int,
    y0: float,
    anchors: list[SectionAnchor],
    section_ranges: dict[int, tuple[int, int]],
) -> int:
    same_page = [anchor for anchor in anchors if anchor.page == page and anchor.y0 <= y0 + 4]
    if same_page:
        return sorted(same_page, key=lambda anchor: anchor.y0)[-1].number

    containing = [
        number
        for number, (start_page, end_page) in section_ranges.items()
        if start_page <= page <= end_page
    ]
    return containing[0] if containing else 1


def classify_image(width: int, height: int, page: int, bbox: tuple[float, float, float, float]) -> str:
    if width >= 450 and height >= 120 and page == 1 and bbox[1] < 120:
        return "logo_encabezado"
    if width <= 80 and height <= 80:
        return "icono_o_marca_pequena"
    if abs(width - height) <= 70 and width >= 100:
        return "pictograma_o_simbolo"
    return "imagen_embebida"


def image_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_extension(extension: str) -> str:
    extension = extension.lower().lstrip(".")
    if extension in {"jpg", "jpeg", "png", "webp", "tiff", "bmp"}:
        return "jpg" if extension == "jpeg" else extension
    return "png"


def ocr_image_bytes(data: bytes) -> str:
    try:
        image = Image.open(BytesIO(data))
        text = pytesseract.image_to_string(image, lang="spa+eng")
        return "\n".join(line.strip() for line in text.splitlines() if line.strip())
    except Exception as exc:  # pragma: no cover - depends on local OCR binaries and image internals
        return f"OCR_ERROR: {type(exc).__name__}: {exc}"


def extract_images(
    pdf_path: Path,
    document_id: str,
    manufacturer: str,
    section_ranges: dict[int, tuple[int, int]],
    assets_root: Path,
) -> list[ExtractedImage]:
    anchors = detect_section_anchors(pdf_path)
    image_dir = assets_root / manufacturer / document_id / "images"
    if image_dir.exists():
        shutil.rmtree(image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[ExtractedImage] = []

    with fitz.open(pdf_path) as document:
        for page_index, page in enumerate(document, start=1):
            for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                xref = image_info[0]
                image = document.extract_image(xref)
                data = image["image"]
                extension = safe_extension(image.get("ext", "png"))
                rects = page.get_image_rects(xref)
                bbox = tuple(float(value) for value in (rects[0] if rects else fitz.Rect(0, 0, 0, 0)))
                width = int(image.get("width") or 0)
                height = int(image.get("height") or 0)
                digest = image_sha256(data)
                image_id = f"{document_id}__p{page_index:03d}_img{image_index:02d}"
                file_name = f"{image_id}.{extension}"
                output_path = image_dir / file_name
                output_path.write_bytes(data)
                section_number = section_for_bbox(page_index, bbox[1], anchors, section_ranges)
                kind = classify_image(width, height, page_index, bbox)
                ocr_text = ocr_image_bytes(data)
                trace_note = (
                    f"Nota de trazabilidad: imagen `{image_id}` extraida de la pagina {page_index}, "
                    f"asociada a la Seccion {section_number} por proximidad espacial y metadatos de pagina. "
                    f"Tipo detectado: {kind}. Hash SHA-256: {digest}."
                )
                extracted.append(
                    ExtractedImage(
                        image_id=image_id,
                        page=page_index,
                        section_number=section_number,
                        file_name=file_name,
                        relative_markdown_path=f"../../assets/{manufacturer}/{document_id}/images/{file_name}",
                        width=width,
                        height=height,
                        bbox=bbox,
                        sha256=digest,
                        kind=kind,
                        ocr_text=ocr_text,
                        trace_note=trace_note,
                    )
                )
    return extracted


def extract_tables(
    pdf_path: Path,
    document_id: str,
    section_ranges: dict[int, tuple[int, int]],
) -> list[ExtractedTable]:
    anchors = detect_section_anchors(pdf_path)
    tables: list[ExtractedTable] = []
    with fitz.open(pdf_path) as document:
        for page_index, page in enumerate(document, start=1):
            for table_index, table in enumerate(page.find_tables().tables, start=1):
                bbox = tuple(float(value) for value in table.bbox)
                section_number = section_for_bbox(page_index, bbox[1], anchors, section_ranges)
                table_id = f"{document_id}__p{page_index:03d}_tbl{table_index:02d}"
                markdown = normalize_table_markdown(table.to_markdown())
                trace_note = (
                    f"Nota de trazabilidad: tabla `{table_id}` extraida de la pagina {page_index}, "
                    f"asociada a la Seccion {section_number} por proximidad espacial y metadatos de pagina."
                )
                tables.append(
                    ExtractedTable(
                        table_id=table_id,
                        page=page_index,
                        section_number=section_number,
                        bbox=bbox,
                        markdown=markdown,
                        trace_note=trace_note,
                    )
                )
    return tables


def normalize_table_markdown(markdown: str) -> str:
    lines = [line.rstrip() for line in markdown.strip().splitlines() if line.strip()]
    return "\n".join(lines).strip()


def group_by_section(items: list[ExtractedImage] | list[ExtractedTable]) -> dict[int, list]:
    grouped: dict[int, list] = {}
    for item in items:
        grouped.setdefault(item.section_number, []).append(item)
    return grouped


def dataclass_list(items: list[ExtractedImage] | list[ExtractedTable]) -> list[dict]:
    return [asdict(item) for item in items]
