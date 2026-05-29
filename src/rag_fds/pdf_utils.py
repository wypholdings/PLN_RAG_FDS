from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class PdfText:
    page_count: int
    page_texts: list[str]
    extraction_errors: list[str]

    @property
    def full_text(self) -> str:
        return "\n\n".join(self.page_texts)

    @property
    def text_chars(self) -> int:
        return len(self.full_text)

    @property
    def pages_with_text(self) -> int:
        return sum(1 for text in self.page_texts if len(text.strip()) >= 80)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_text_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.casefold()).strip()
    return hashlib.sha256(normalized.encode("utf-8", errors="ignore")).hexdigest()


def read_pdf_text(path: Path) -> PdfText:
    errors: list[str] = []
    page_texts: list[str] = []
    try:
        reader = PdfReader(str(path))
        for index, page in enumerate(reader.pages, start=1):
            try:
                page_texts.append(page.extract_text() or "")
            except Exception as exc:  # pragma: no cover - depends on PDF internals
                page_texts.append("")
                errors.append(f"page {index}: {type(exc).__name__}: {exc}")
        return PdfText(
            page_count=len(reader.pages),
            page_texts=page_texts,
            extraction_errors=errors,
        )
    except Exception as exc:
        return PdfText(
            page_count=0,
            page_texts=[],
            extraction_errors=[f"document: {type(exc).__name__}: {exc}"],
        )


def guess_product_name(text: str, fallback: str) -> str:
    candidates = []
    for raw_line in text.splitlines()[:25]:
        line = " ".join(raw_line.split())
        if not line:
            continue
        normalized = line.lower()
        if normalized.startswith(
            (
                "ficha de datos",
                "hoja de datos",
                "fecha de emision",
                "fecha de emisión",
                "msds no",
                "versión",
                "version",
                "seccion",
                "sección",
            )
        ):
            continue
        if re.fullmatch(r"\d+\s*/\s*\d+", line):
            continue
        if 4 <= len(line) <= 120:
            candidates.append(line)
    return candidates[0] if candidates else fallback
