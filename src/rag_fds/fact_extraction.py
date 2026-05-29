from __future__ import annotations

import re
from dataclasses import dataclass

from .vector_index import SearchResult


@dataclass(frozen=True)
class LiteralAnswer:
    answer: str
    reason: str


def source_label(result: SearchResult) -> str:
    chunk = result.chunk
    return (
        f"[FUENTE {result.rank}] {chunk['source_file']} | "
        f"seccion {chunk['section_number']} | paginas {chunk['page_start']}-{chunk['page_end']} | "
        f"{chunk['chunk_id']}"
    )


def normalized(text: str) -> str:
    text = text.lower()
    return re.sub(r"\s+", " ", text).strip()


def literal_lines(content: str, terms: list[str], limit: int = 8) -> list[str]:
    output: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        low = normalized(line)
        if any(term in low for term in terms):
            output.append(line)
        if len(output) >= limit:
            break
    return output


def table_answer(headers: list[str], rows: list[list[str]]) -> str:
    def cell(value: str) -> str:
        return value.replace("|", "&#124;").replace("\n", " ").replace("<br>", "; ")

    lines = [
        "| " + " | ".join(cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(cell(value) for value in row) + " |")
    return "\n".join(lines)


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        clean = " ".join(value.split()).strip(" ;")
        if clean and clean not in seen:
            seen.add(clean)
            output.append(clean)
    return output


def first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else "no reportado en el fragmento"


def extract_emergency_phone(results: list[SearchResult]) -> LiteralAnswer | None:
    rows: list[list[str]] = []
    for result in results:
        content = result.chunk["content"]
        if "cisproquim" not in normalized(content):
            continue
        bogota = re.search(r"Bogot[áa]\s*:\s*([^\n]+)", content, flags=re.IGNORECASE)
        resto = re.search(r"Resto del pa[íi]s\s*:\s*([^\n]+)", content, flags=re.IGNORECASE)
        if not bogota and not resto:
            continue
        rows.append(
            [
                source_label(result),
                "CISPROQUIM",
                bogota.group(1).strip() if bogota else "no reportado en el fragmento",
                resto.group(1).strip() if resto else "no reportado en el fragmento",
            ]
        )
    if not rows:
        return None
    return LiteralAnswer(
        answer=table_answer(["Fuente", "Entidad", "Bogota", "Resto del pais"], rows),
        reason="telefono_emergencia_extraido_literalmente",
    )


def extract_section_trace(question: str, results: list[SearchResult]) -> LiteralAnswer | None:
    q = normalized(question)
    if "que seccion" not in q and "en que seccion" not in q:
        return None
    if not results:
        return None
    result = results[0]
    chunk = result.chunk
    answer = table_answer(
        ["Fuente", "Seccion", "Titulo", "Paginas"],
        [[source_label(result), str(chunk["section_number"]), chunk["section_title"], f"{chunk['page_start']}-{chunk['page_end']}"]],
    )
    return LiteralAnswer(answer=answer, reason="trazabilidad_seccion_extraida")


def extract_provider_phone(results: list[SearchResult]) -> LiteralAnswer | None:
    rows: list[list[str]] = []
    for result in results:
        content = result.chunk["content"]
        matches = re.findall(r"(?:N[úu]mero de Tel[ée]fono|Tel[ée]fono)\s*:\s*([^\n]+)", content, flags=re.IGNORECASE)
        matches = [match.strip() for match in matches if "cisproquim" not in match.lower()]
        if matches:
            rows.append([source_label(result), " / ".join(matches[:2])])
    if not rows:
        return None
    return LiteralAnswer(
        answer=table_answer(["Fuente", "Telefono proveedor"], rows),
        reason="telefono_proveedor_extraido_literalmente",
    )


def extract_transport(results: list[SearchResult]) -> LiteralAnswer | None:
    rows: list[list[str]] = []
    for result in results:
        if int(result.chunk["section_number"]) != 14:
            continue
        content = result.chunk["content"]
        if "onu" not in normalized(content) and "un " not in normalized(content):
            continue
        rows.append(
            [
                source_label(result),
                first_match(r"(?:N[úu]mero ONU|No\. UN/ID)\s*:\s*([^\n]+)", content),
                first_match(r"Clase\s*:\s*([^\n]+)", content),
                first_match(r"Grupo de embalaje\s*:\s*([^\n]+)", content),
            ]
        )
    if not rows:
        return None
    return LiteralAnswer(
        answer=table_answer(["Fuente", "Numero ONU", "Clase", "Grupo de embalaje"], rows),
        reason="transporte_extraido_literalmente",
    )


def extract_cas_components(results: list[SearchResult]) -> LiteralAnswer | None:
    rows: list[list[str]] = []
    cas_pattern = re.compile(r"\b\d{2,7}-\d{2}-\d\b")
    for result in results:
        if int(result.chunk["section_number"]) != 3:
            continue
        candidates: list[str] = []
        for raw_line in result.chunk["content"].splitlines():
            line = raw_line.strip()
            if not cas_pattern.search(line):
                continue
            if line.startswith("|"):
                cells = [cell.strip() for cell in line.strip("|").split("|") if cell.strip()]
                candidates.extend(cells)
            else:
                candidates.append(line)
        lines = unique_preserve_order(candidates)
        if lines:
            rows.append([source_label(result), "; ".join(lines[:10])])
    if not rows:
        return None
    return LiteralAnswer(
        answer=table_answer(["Fuente", "Componentes/CAS literales"], rows),
        reason="cas_extraido_literalmente",
    )


def extract_ppe(results: list[SearchResult]) -> LiteralAnswer | None:
    rows: list[list[str]] = []
    for result in results:
        if int(result.chunk["section_number"]) != 8:
            continue
        lines = literal_lines(
            result.chunk["content"],
            ["guantes", "gafas", "respir", "proteccion", "protección", "epp", "exposicion", "exposición"],
            limit=12,
        )
        if lines:
            rows.append([source_label(result), "<br>".join(lines)])
    if not rows:
        return None
    return LiteralAnswer(
        answer=table_answer(["Fuente", "EPP / controles literales"], rows),
        reason="epp_extraido_literalmente",
    )


def extract_image_trace(results: list[SearchResult]) -> LiteralAnswer | None:
    rows: list[list[str]] = []
    for result in results:
        lines = literal_lines(
            result.chunk["content"],
            ["[imagen", "tipo:", "nota de trazabilidad", "texto ocr", "hash sha-256"],
            limit=12,
        )
        if lines:
            rows.append([source_label(result), "<br>".join(lines)])
    if not rows:
        return None
    return LiteralAnswer(
        answer=table_answer(["Fuente", "Metadatos visuales extraidos"], rows),
        reason="metadatos_imagen_extraidos",
    )


def extract_literal_answer(question: str, results: list[SearchResult]) -> LiteralAnswer | None:
    q = normalized(question)
    section_trace = extract_section_trace(question, results)
    if section_trace is not None:
        return section_trace
    if "cisproquim" in q or ("telefono" in q and "emerg" in q):
        return extract_emergency_phone(results)
    if "telefono" in q and ("proveedor" in q or "sika colombia" in q or "fabricante" in q):
        return extract_provider_phone(results)
    if "cas" in q or "componente" in q or "composicion" in q or "composición" in q:
        return extract_cas_components(results)
    if "onu" in q or "transporte" in q or "embalaje" in q or "clase" in q:
        return extract_transport(results)
    if "epp" in q or "proteccion personal" in q or "protección personal" in q or "guantes" in q:
        return extract_ppe(results)
    if "logo" in q or "pictograma" in q or "imagen" in q or "ocr" in q:
        return extract_image_trace(results)
    return None
