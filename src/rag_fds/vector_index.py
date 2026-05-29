from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@dataclass(frozen=True)
class SearchResult:
    rank: int
    score: float
    chunk: dict


def load_chunks(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def chunk_embedding_text(chunk: dict) -> str:
    return "\n".join(
        [
            f"Producto: {chunk['product']}",
            f"Documento: {chunk['source_file']}",
            f"Seccion {chunk['section_number']}: {chunk['section_title']}",
            f"Paginas: {chunk['page_start']}-{chunk['page_end']}",
            chunk["content"],
        ]
    )


@lru_cache(maxsize=2)
def load_model(model_name: str = DEFAULT_EMBEDDING_MODEL) -> SentenceTransformer:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    return SentenceTransformer(model_name, local_files_only=True)


def encode_texts(model: SentenceTransformer, texts: list[str], batch_size: int = 32) -> np.ndarray:
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(embeddings, dtype=np.float32)


def build_index(
    chunks_path: Path,
    index_dir: Path,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
) -> dict:
    chunks = load_chunks(chunks_path)
    model = load_model(model_name)
    texts = [chunk_embedding_text(chunk) for chunk in chunks]
    embeddings = encode_texts(model, texts)
    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=1,
    )
    lexical_matrix = vectorizer.fit_transform(texts)

    index_dir.mkdir(parents=True, exist_ok=True)
    np.save(index_dir / "embeddings.npy", embeddings)
    joblib.dump(vectorizer, index_dir / "tfidf_vectorizer.joblib")
    joblib.dump(lexical_matrix, index_dir / "tfidf_matrix.joblib")
    (index_dir / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    config = {
        "model_name": model_name,
        "chunks_path": str(chunks_path),
        "chunk_count": len(chunks),
        "embedding_dim": int(embeddings.shape[1]) if embeddings.size else 0,
        "normalized": True,
        "similarity": "hybrid_cosine_tfidf",
        "semantic_weight": 0.55,
        "lexical_weight": 0.25,
        "term_coverage_weight": 0.20,
        "section_match_boost": 0.18,
    }
    (index_dir / "index_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump({"model_name": model_name}, index_dir / "model_ref.joblib")
    return config


def load_index(index_dir: Path) -> tuple[dict, list[dict], np.ndarray, TfidfVectorizer, object]:
    config = json.loads((index_dir / "index_config.json").read_text(encoding="utf-8"))
    chunks = json.loads((index_dir / "chunks.json").read_text(encoding="utf-8"))
    embeddings = np.load(index_dir / "embeddings.npy")
    vectorizer = joblib.load(index_dir / "tfidf_vectorizer.joblib")
    lexical_matrix = joblib.load(index_dir / "tfidf_matrix.joblib")
    return config, chunks, embeddings, vectorizer, lexical_matrix


def search(index_dir: Path, query: str, top_k: int = 5) -> list[SearchResult]:
    config, chunks, embeddings, vectorizer, lexical_matrix = load_index(index_dir)
    model = load_model(config["model_name"])
    query_embedding = encode_texts(model, [query])[0]
    semantic_scores = embeddings @ query_embedding
    query_lexical = vectorizer.transform([query])
    lexical_scores = (lexical_matrix @ query_lexical.T).toarray().ravel()
    semantic_weight = float(config.get("semantic_weight", 0.55))
    lexical_weight = float(config.get("lexical_weight", 0.25))
    term_coverage_weight = float(config.get("term_coverage_weight", 0.20))
    coverage_scores = np.asarray([term_coverage_score(query, chunk["content"]) for chunk in chunks])
    scores = semantic_weight * semantic_scores + lexical_weight * lexical_scores + term_coverage_weight * coverage_scores
    requested_section = requested_section_number(query) or inferred_section_number(query)
    if requested_section is not None:
        section_boost = float(config.get("section_match_boost", 0.18))
        for index, chunk in enumerate(chunks):
            if int(chunk["section_number"]) == requested_section:
                scores[index] += section_boost * 2
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [
        SearchResult(rank=rank, score=float(scores[index]), chunk=chunks[int(index)])
        for rank, index in enumerate(top_indices, start=1)
    ]


def normalize_for_match(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(character for character in text if not unicodedata.combining(character))
    return text


def important_terms(query: str) -> list[str]:
    normalized = normalize_for_match(query)
    stopwords = {
        "para",
        "sobre",
        "cual",
        "cuales",
        "numero",
        "seccion",
        "informacion",
        "datos",
    }
    terms = []
    for term in re.findall(r"[a-z0-9]{4,}", normalized):
        if term not in stopwords:
            terms.append(term)
    return sorted(set(terms))


def term_coverage_score(query: str, content: str) -> float:
    terms = important_terms(query)
    if not terms:
        return 0.0
    normalized_content = normalize_for_match(content)
    found = sum(1 for term in terms if term in normalized_content)
    return found / len(terms)


def requested_section_number(query: str) -> int | None:
    normalized = normalize_for_match(query)
    match = re.search(r"\bseccion\s+(1[0-6]|[1-9])\b", normalized)
    if not match:
        return None
    return int(match.group(1))


def inferred_section_number(query: str) -> int | None:
    normalized = normalize_for_match(query)
    title_hints = [
        (1, ["identificacion", "proveedor", "fabricante", "telefono", "uso recomendado", "uso del producto"]),
        (2, ["identificacion de los peligros", "peligros"]),
        (3, ["composicion", "componentes", "cas"]),
        (4, ["primeros auxilios"]),
        (5, ["incendios", "lucha contra incendios"]),
        (6, ["vertido accidental", "derrame", "vertidos"]),
        (7, ["manipulacion", "almacenamiento"]),
        (8, ["controles de exposicion", "proteccion personal", "epp", "guantes", "respirador"]),
        (9, ["propiedades fisicas", "propiedades quimicas", "fisicoquimicas", "densidad", "punto de inflamacion"]),
        (10, ["estabilidad", "reactividad"]),
        (11, ["toxicologica", "toxicologia"]),
        (12, ["ecologica", "ecologia"]),
        (13, ["eliminacion"]),
        (14, ["transporte", "numero onu", "onu", "grupo de embalaje"]),
        (15, ["reglamentaria", "regulacion"]),
        (16, ["otra informacion", "otras informaciones"]),
    ]
    matches: list[tuple[int, int]] = []
    for number, hints in title_hints:
        score = sum(1 for hint in hints if hint in normalized)
        if score:
            matches.append((score, number))
    if not matches:
        return None
    return sorted(matches, reverse=True)[0][1]
