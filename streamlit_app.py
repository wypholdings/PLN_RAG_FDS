from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from rag_fds.chunking import chunks_from_metadata, load_metadata_files, write_jsonl
from rag_fds.config import MANUFACTURERS, PROCESSED_DIR, PROJECT_ROOT
from rag_fds.fact_extraction import extract_literal_answer
from rag_fds.generation import answer_question
from rag_fds.markdown_converter import convert_pdf, write_converted_document
from rag_fds.vector_index import build_index, search


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return text.strip("-") or "uploads"


def list_ready_indexes() -> dict[str, Path]:
    result: dict[str, Path] = {}
    for manufacturer in MANUFACTURERS:
        index_dir = PROJECT_ROOT / "data" / "indexes" / manufacturer.lower()
        if (index_dir / "index_config.json").exists():
            result[manufacturer] = index_dir
    return result


def process_uploaded_pdfs(files: list, collection_name: str) -> dict:
    collection_slug = slugify(collection_name)
    base_dir = PROJECT_ROOT / "data" / "runtime_uploads" / collection_slug
    source_dir = base_dir / "source"
    processed_dir = base_dir / "processed"
    assets_dir = processed_dir / "assets"
    manufacturer = f"UPLOAD_{collection_slug}"

    source_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    seen_hashes: set[str] = set()

    for uploaded in files:
        target = source_dir / uploaded.name
        target.write_bytes(uploaded.getvalue())
        document = convert_pdf(target, manufacturer=manufacturer, assets_root=assets_dir)
        if document.text_sha256 in seen_hashes:
            rows.append({"archivo": uploaded.name, "estado": "duplicado", "document_id": document.document_id})
            continue
        seen_hashes.add(document.text_sha256)
        write_converted_document(document, processed_dir)
        rows.append(
            {
                "archivo": uploaded.name,
                "estado": "convertido",
                "document_id": document.document_id,
                "paginas": document.page_count,
                "secciones": len(document.sections),
                "tablas": len(document.tables),
                "imagenes": len(document.images),
            }
        )

    metadata_dir = processed_dir / "metadata" / manufacturer
    metadata_items = load_metadata_files(metadata_dir)
    chunks = []
    for metadata in metadata_items:
        chunks.extend(chunks_from_metadata(metadata))

    chunks_path = processed_dir / "chunks" / f"{collection_slug}_chunks.jsonl"
    write_jsonl(chunks, chunks_path)

    index_dir = base_dir / "index"
    build_index(chunks_path=chunks_path, index_dir=index_dir)
    summary = {
        "collection_name": collection_name,
        "collection_slug": collection_slug,
        "manufacturer_runtime": manufacturer,
        "base_dir": str(base_dir),
        "documents": len(metadata_items),
        "chunks": len(chunks),
        "index_dir": str(index_dir),
        "processed_at": datetime.now().isoformat(timespec="seconds"),
    }
    (base_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"rows": rows, "summary": summary, "index_dir": index_dir}


def show_sources(sources: list[dict]) -> None:
    if not sources:
        return
    st.markdown("**Fuentes recuperadas**")
    st.dataframe(sources, hide_index=True, use_container_width=True)


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def build_structured_answer(question: str, raw_results: list) -> str | None:
    q = question.lower()
    chunks = [result.chunk for result in raw_results]
    texts = [_compact(chunk.get("content", "")) for chunk in chunks]

    # Caso 1: telefono de emergencia
    if "cisproquim" in q or ("telefono" in q and "emerg" in q):
        matches = []
        for idx, text in enumerate(texts):
            if "cisproquim" not in text.lower():
                continue
            bogota = re.search(r"Bogot[áa]\s*:\s*([0-9\s/()-]+)", text, flags=re.IGNORECASE)
            resto = re.search(r"Resto del pa[íi]s\s*:\s*([0-9\s/-]+)", text, flags=re.IGNORECASE)
            if bogota or resto:
                chunk = chunks[idx]
                matches.append(
                    {
                        "source": f"[FUENTE {idx + 1}]",
                        "doc": chunk["source_file"],
                        "bogota": bogota.group(1).strip() if bogota else "no reportado",
                        "resto": resto.group(1).strip() if resto else "no reportado",
                        "sec": chunk["section_number"],
                        "pages": f"{chunk['page_start']}-{chunk['page_end']}",
                        "chunk_id": chunk["chunk_id"],
                    }
                )
        if not matches:
            return "No hay informacion suficiente en los fragmentos recuperados."
        lines = [
            "| Fuente | Documento | Bogotá | Resto país | Sección | Páginas | chunk_id |",
            "|---|---|---|---|---:|---|---|",
        ]
        for item in matches:
            lines.append(
                f"| {item['source']} | {item['doc']} | {item['bogota']} | {item['resto']} | {item['sec']} | {item['pages']} | {item['chunk_id']} |"
            )
        return "\n".join(lines)

    # Caso 2: ONU / clase / grupo de embalaje (seccion 14)
    if "onu" in q or "clase" in q or "embalaje" in q or "seccion 14" in q:
        rows = []
        for idx, text in enumerate(texts):
            chunk = chunks[idx]
            onu = re.search(r"(?:N[úu]mero\s+ONU|UN)\s*[:\-]?\s*([A-Z0-9]+)", text, flags=re.IGNORECASE)
            clase = re.search(r"Clase(?:\(s\))?\s*[:\-]?\s*([0-9A-Za-z\.\-]+)", text, flags=re.IGNORECASE)
            grupo = re.search(r"Grupo de embalaje\s*[:\-]?\s*([A-Za-z0-9\-]+)", text, flags=re.IGNORECASE)
            if onu or clase or grupo:
                rows.append(
                    {
                        "source": f"[FUENTE {idx + 1}]",
                        "doc": chunk["source_file"],
                        "onu": onu.group(1).strip() if onu else "no reportado",
                        "clase": clase.group(1).strip() if clase else "no reportado",
                        "grupo": grupo.group(1).strip() if grupo else "no reportado",
                        "sec": chunk["section_number"],
                        "pages": f"{chunk['page_start']}-{chunk['page_end']}",
                        "chunk_id": chunk["chunk_id"],
                    }
                )
        if not rows:
            return "No hay informacion suficiente en los fragmentos recuperados."
        lines = [
            "| Fuente | Documento | ONU | Clase | Grupo embalaje | Sección | Páginas | chunk_id |",
            "|---|---|---|---|---|---:|---|---|",
        ]
        for item in rows:
            lines.append(
                f"| {item['source']} | {item['doc']} | {item['onu']} | {item['clase']} | {item['grupo']} | {item['sec']} | {item['pages']} | {item['chunk_id']} |"
            )
        return "\n".join(lines)

    return None


def main() -> None:
    st.set_page_config(page_title="RAG_FDS Demo", layout="wide")
    st.title("RAG_FDS Demo")

    if "chat" not in st.session_state:
        st.session_state.chat = []
    if "active_index_dir" not in st.session_state:
        st.session_state.active_index_dir = None
    if "active_corpus_label" not in st.session_state:
        st.session_state.active_corpus_label = None

    ready_indexes = list_ready_indexes()
    with st.sidebar:
        st.header("Corpus")
        mode = st.radio("Origen", options=["Preprocesado", "Subir PDFs manualmente"], horizontal=False)
        if mode == "Preprocesado":
            if not ready_indexes:
                st.warning("No hay indices preprocesados listos.")
            else:
                selected = st.selectbox("Fabricante", options=list(ready_indexes.keys()))
                if st.button("Usar este corpus", use_container_width=True):
                    st.session_state.active_index_dir = ready_indexes[selected]
                    st.session_state.active_corpus_label = f"{selected} (preprocesado)"
                    st.success(f"Corpus activo: {st.session_state.active_corpus_label}")
        else:
            collection_name = st.text_input("Nombre de colección", value="nueva_coleccion")
            uploaded_files = st.file_uploader(
                "Carga uno o varios PDFs",
                type=["pdf"],
                accept_multiple_files=True,
            )
            if st.button("Procesar PDFs", use_container_width=True, disabled=not uploaded_files):
                with st.spinner("Convirtiendo, chunking e indexando..."):
                    result = process_uploaded_pdfs(uploaded_files, collection_name)
                st.session_state.active_index_dir = result["index_dir"]
                st.session_state.active_corpus_label = f"{collection_name} (subido manualmente)"
                st.success(f"Corpus activo: {st.session_state.active_corpus_label}")
                st.dataframe(result["rows"], hide_index=True, use_container_width=True)
                st.json(result["summary"])

        st.divider()
        st.header("Generación")
        ollama_base_url = st.text_input("OLLAMA_BASE_URL", value="http://127.0.0.1:11434")
        ollama_model = st.text_input("Modelo", value="qwen2.5:3b")
        top_k = st.slider("Top-K", min_value=1, max_value=8, value=3)
        max_chars = st.slider("Máx. caracteres por fuente", min_value=600, max_value=3000, value=1700, step=100)
        timeout_seconds = st.slider("Timeout (segundos)", min_value=60, max_value=600, value=300, step=30)
        high_precision_mode = st.toggle("Modo alta precisión (determinístico)", value=True)
        if st.button("Limpiar historial", use_container_width=True):
            st.session_state.chat = []

    if not st.session_state.active_index_dir:
        st.info("Selecciona un corpus en la barra lateral para comenzar.")
        return

    st.caption(f"Corpus activo: {st.session_state.active_corpus_label}")
    question = st.text_input("Pregunta", placeholder="Ejemplo: ¿Cuál es el teléfono de emergencia CISPROQUIM?")
    ask = st.button("Preguntar", type="primary")

    if ask and question.strip():
        try:
            with st.spinner("Recuperando evidencia y generando respuesta..."):
                raw_results = search(Path(st.session_state.active_index_dir), question.strip(), top_k=top_k)
                if high_precision_mode:
                    literal = extract_literal_answer(question.strip(), raw_results)
                    if literal is not None:
                        answer_text = literal.answer
                        answer_sources = [
                            {
                                "rank": result.rank,
                                "score": round(result.score, 6),
                                "chunk_id": result.chunk["chunk_id"],
                                "document": result.chunk["source_file"],
                                "section_number": result.chunk["section_number"],
                                "section_title": result.chunk["section_title"],
                                "page_start": result.chunk["page_start"],
                                "page_end": result.chunk["page_end"],
                            }
                            for result in raw_results
                        ]
                    else:
                        answer = answer_question(
                            index_dir=Path(st.session_state.active_index_dir),
                            question=question.strip(),
                            top_k=top_k,
                            model=ollama_model,
                            base_url=ollama_base_url,
                            timeout_seconds=timeout_seconds,
                            max_chars_per_source=max_chars,
                        )
                        answer_text = answer.answer
                        answer_sources = answer.sources
                else:
                    answer = answer_question(
                        index_dir=Path(st.session_state.active_index_dir),
                        question=question.strip(),
                        top_k=top_k,
                        model=ollama_model,
                        base_url=ollama_base_url,
                        timeout_seconds=timeout_seconds,
                        max_chars_per_source=max_chars,
                    )
                    answer_text = answer.answer
                    answer_sources = answer.sources
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            st.error(
                "No se pudo completar la generación con Ollama remoto en el tiempo esperado. "
                "Reintenta con Top-K 2-3 y max chars 1000-1700, o verifica Ollama local."
            )
            st.code(str(exc))
            return
        trace_rows = []
        for result in raw_results:
            chunk = result.chunk
            trace_rows.append(
                {
                    "rank": result.rank,
                    "score": round(result.score, 6),
                    "documento": chunk["source_file"],
                    "seccion": chunk["section_number"],
                    "titulo": chunk["section_title"],
                    "paginas": f"{chunk['page_start']}-{chunk['page_end']}",
                    "chunk_id": chunk["chunk_id"],
                    "extracto": chunk["content"][:300],
                }
            )
        st.session_state.chat.append(
            {
                "question": question.strip(),
                "answer": answer_text,
                "sources": answer_sources,
                "trace_rows": trace_rows,
                "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    for turn in reversed(st.session_state.chat):
        st.markdown(f"### {turn['at']}")
        st.markdown(f"**Pregunta:** {turn['question']}")
        st.markdown("**Respuesta:**")
        st.write(turn["answer"])
        show_sources(turn["sources"])
        with st.expander("Ver trazabilidad detallada"):
            st.dataframe(turn["trace_rows"], hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
