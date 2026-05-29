from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


SECTION_TITLES = {
    1: "Identificacion de la sustancia o la mezcla y de la sociedad o la empresa",
    2: "Identificacion de los peligros",
    3: "Composicion/informacion sobre los componentes",
    4: "Primeros auxilios",
    5: "Medidas de lucha contra incendios",
    6: "Medidas en caso de vertido accidental",
    7: "Manipulacion y almacenamiento",
    8: "Controles de exposicion/proteccion individual",
    9: "Propiedades fisicas y quimicas",
    10: "Estabilidad y reactividad",
    11: "Informacion toxicologica",
    12: "Informacion ecologica",
    13: "Consideraciones relativas a la eliminacion",
    14: "Informacion relativa al transporte",
    15: "Informacion reglamentaria",
    16: "Otra informacion",
}


SECTION_PATTERN = re.compile(
    r"(?im)(?:^|\n)\s*(?:secci[oó]n|section)\s*0?(1[0-6]|[1-9])\s*[:.\-]?\s*([^\n]{0,180})"
)


@dataclass(frozen=True)
class SectionHit:
    number: int
    title: str
    page: int
    start: int


def normalize_text(value: str) -> str:
    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ñ": "n",
        "Á": "A",
        "É": "E",
        "Í": "I",
        "Ó": "O",
        "Ú": "U",
        "Ñ": "N",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def detect_sections(page_texts: Iterable[str]) -> list[SectionHit]:
    return deduplicate_sections(iter_section_hits(page_texts))


def iter_section_hits(page_texts: Iterable[str]) -> list[SectionHit]:
    hits: list[SectionHit] = []
    for page_number, text in enumerate(page_texts, start=1):
        normalized = normalize_text(text or "")
        for match in SECTION_PATTERN.finditer(normalized):
            number = int(match.group(1))
            title = " ".join((match.group(2) or "").split())
            if sum(character.isalpha() for character in title) < 3:
                continue
            hits.append(
                SectionHit(
                    number=number,
                    title=title,
                    page=page_number,
                    start=match.start(),
                )
            )
    return hits


def deduplicate_sections(hits: Iterable[SectionHit]) -> list[SectionHit]:
    first_by_number: dict[int, SectionHit] = {}
    for hit in hits:
        if hit.number not in first_by_number:
            first_by_number[hit.number] = hit
    return [first_by_number[number] for number in sorted(first_by_number)]


def missing_sections(hits: Iterable[SectionHit]) -> list[int]:
    found = {hit.number for hit in hits}
    return [number for number in range(1, 17) if number not in found]
