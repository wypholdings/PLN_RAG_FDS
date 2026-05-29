from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from .fact_extraction import extract_literal_answer
from .vector_index import SearchResult, search


DEFAULT_OLLAMA_MODEL = "qwen2.5:3b"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"


@dataclass(frozen=True)
class RagAnswer:
    question: str
    answer: str
    sources: list[dict]
    prompt: str


def resolve_ollama_base_url() -> str:
    env_url = os.environ.get("OLLAMA_BASE_URL")
    if env_url:
        return env_url.rstrip("/")
    runtime_path = Path("data/runtime/ollama_endpoint.json")
    if runtime_path.exists():
        payload = json.loads(runtime_path.read_text(encoding="utf-8"))
        endpoint = payload.get("ollama_base_url")
        if endpoint:
            return str(endpoint).rstrip("/")
    return DEFAULT_OLLAMA_BASE_URL


def build_sources(results: list[SearchResult]) -> list[dict]:
    sources = []
    for result in results:
        chunk = result.chunk
        sources.append(
            {
                "rank": result.rank,
                "score": round(result.score, 6),
                "chunk_id": chunk["chunk_id"],
                "document": chunk["source_file"],
                "product": chunk["product"],
                "section_number": chunk["section_number"],
                "section_title": chunk["section_title"],
                "page_start": chunk["page_start"],
                "page_end": chunk["page_end"],
            }
        )
    return sources


def build_context(results: list[SearchResult], max_chars_per_source: int = 1800) -> str:
    blocks: list[str] = []
    for result in results:
        chunk = result.chunk
        content = chunk["content"][:max_chars_per_source].strip()
        blocks.append(
            "\n".join(
                [
                    f"[FUENTE {result.rank}]",
                    f"chunk_id: {chunk['chunk_id']}",
                    f"documento: {chunk['source_file']}",
                    f"producto: {chunk['product']}",
                    f"seccion: {chunk['section_number']} - {chunk['section_title']}",
                    f"paginas: {chunk['page_start']}-{chunk['page_end']}",
                    "contenido:",
                    content,
                ]
            )
        )
    return "\n\n".join(blocks)


def build_prompt(question: str, results: list[SearchResult], max_chars_per_source: int = 1800) -> str:
    context = build_context(results, max_chars_per_source=max_chars_per_source)
    return (
        "Eres un asistente tecnico de Fichas de Datos de Seguridad (FDS).\n"
        "Responde solo con evidencia del CONTEXTO.\n"
        "No cambies numeros, unidades, signos, puntos, comas, porcentajes, telefonos, codigos CAS ni codigos ONU.\n"
        "Cuando cites un valor tecnico, copialo literalmente desde el CONTEXTO.\n"
        "No normalices magnitudes ni conviertas unidades.\n"
        "Primero entrega una respuesta directa y literal a la pregunta.\n"
        "Si la pregunta pide telefono, CAS, ONU, porcentaje, fecha o valor, copia exactamente el dato del contexto.\n"
        "Si el contexto no es suficiente, responde exactamente: "
        "\"No hay informacion suficiente en los fragmentos recuperados.\"\n"
        "No inventes datos.\n"
        "Siempre incluye al final una seccion titulada 'Fuentes' con viñetas en este formato:\n"
        "- [FUENTE N] documento | seccion X | paginas A-B | chunk_id\n\n"
        f"PREGUNTA:\n{question}\n\n"
        f"CONTEXTO:\n{context}"
    )


def call_ollama(prompt: str, model: str, base_url: str, timeout_seconds: int = 120) -> str:
    url = f"{base_url.rstrip('/')}/api/generate"
    response = requests.post(
        url,
        json={
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": 0,
                "top_p": 0.1,
                "repeat_penalty": 1.05,
                "num_ctx": 4096,
            },
            "keep_alive": "10m",
        },
        timeout=(20, timeout_seconds),
        stream=True,
    )
    response.raise_for_status()
    pieces: list[str] = []
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        payload = json.loads(line)
        token = payload.get("response", "")
        if token:
            pieces.append(token)
        if payload.get("done") is True:
            break
    text = "".join(pieces).strip()
    if not text:
        raise RuntimeError("Ollama devolvio respuesta vacia.")
    return text


def answer_question(
    index_dir: Path,
    question: str,
    top_k: int = 4,
    model: str = DEFAULT_OLLAMA_MODEL,
    base_url: str | None = None,
    timeout_seconds: int = 240,
    max_chars_per_source: int = 1800,
) -> RagAnswer:
    resolved_base_url = base_url.rstrip("/") if base_url else resolve_ollama_base_url()
    initial_results = search(index_dir, question, top_k=top_k)
    literal = extract_literal_answer(question, initial_results)
    if literal is not None:
        prompt = build_prompt(question, initial_results, max_chars_per_source=max_chars_per_source)
        return RagAnswer(
            question=question,
            answer=literal.answer,
            sources=build_sources(initial_results),
            prompt=prompt,
        )
    attempts = [
        (top_k, max_chars_per_source),
        (max(1, top_k - 1), min(max_chars_per_source, 1400)),
        (max(1, top_k - 2), min(max_chars_per_source, 1000)),
    ]
    last_error: Exception | None = None
    for attempt_index, (attempt_top_k, attempt_chars) in enumerate(attempts, start=1):
        try:
            results = search(index_dir, question, top_k=attempt_top_k)
            prompt = build_prompt(question, results, max_chars_per_source=attempt_chars)
            answer = call_ollama(
                prompt=prompt,
                model=model,
                base_url=resolved_base_url,
                timeout_seconds=timeout_seconds,
            )
            return RagAnswer(
                question=question,
                answer=answer,
                sources=build_sources(results),
                prompt=prompt,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_error = exc
            if attempt_index < len(attempts):
                time.sleep(1.5 * attempt_index)
                continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError("No se pudo generar respuesta con Ollama.")
