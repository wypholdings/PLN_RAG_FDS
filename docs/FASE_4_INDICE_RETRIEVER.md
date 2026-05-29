# Fase 4 - Indice vectorial y retriever local

## Objetivo

Construir un indice local sobre los chunks SIKA y permitir busqueda semantica con trazabilidad completa hacia documento, seccion, paginas, tablas, imagenes y OCR.

## Componentes

- `src/rag_fds/vector_index.py`
- `scripts/build_vector_index.py`
- `scripts/retrieve.py`
- `scripts/test_retrieval.py`

## Modelo de embeddings

Modelo local descargado:

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

Caracteristicas:

- multilingue,
- ejecuta localmente,
- embeddings normalizados,
- dimension 384.

El retriever fuerza modo offline/local al cargar el modelo para no depender de red durante la demo.

## Estrategia de recuperacion

Se usa recuperacion hibrida:

- embeddings semanticos con Sentence Transformers,
- TF-IDF local para coincidencia lexica,
- cobertura de terminos importantes,
- boost cuando la pregunta menciona una seccion normativa explicita.

Esta mezcla mejora preguntas tecnicas con codigos, entidades y terminos exactos como `CISPROQUIM`, `Numero ONU`, `CAS` o `Seccion 8`.

## Comandos

```bash
python scripts/build_vector_index.py --manufacturer SIKA
python scripts/retrieve.py --manufacturer SIKA --query "telefono de emergencia CISPROQUIM" --top-k 3
python scripts/test_retrieval.py --manufacturer SIKA
```

## Salidas generadas

Indice:

- `data/indexes/sika/embeddings.npy`
- `data/indexes/sika/chunks.json`
- `data/indexes/sika/index_config.json`
- `data/indexes/sika/tfidf_vectorizer.joblib`
- `data/indexes/sika/tfidf_matrix.joblib`
- `data/indexes/sika/model_ref.joblib`

Reportes:

- `data/reports/retrieval_test_report_sika.csv`
- `data/reports/retrieval_test_summary_sika.json`

## Resultado del indice

```json
{
  "chunk_count": 224,
  "embedding_dim": 384,
  "normalized": true,
  "similarity": "hybrid_cosine_tfidf",
  "semantic_weight": 0.55,
  "lexical_weight": 0.25,
  "term_coverage_weight": 0.2,
  "section_match_boost": 0.18
}
```

## Pruebas de recuperacion

```json
{
  "manufacturer": "SIKA",
  "tests": 5,
  "top1_section_passed": 5,
  "topk_section_passed": 5,
  "required_terms_passed": 5,
  "status": "pass"
}
```

Consultas probadas:

- telefono de emergencia CISPROQUIM -> seccion 1.
- equipo de proteccion personal guantes gafas respirador seccion 8 -> seccion 8.
- numero ONU transporte clase grupo de embalaje -> seccion 14.
- composicion componentes CAS concentracion -> seccion 3.
- propiedades fisicas quimicas punto de inflamacion densidad -> seccion 9.

## Siguiente fase

Implementar generacion con Ollama. El LLM recibira solo los chunks recuperados y debera responder con fuentes obligatorias. Si la evidencia recuperada no sustenta la respuesta, el sistema debe responder que no hay informacion suficiente en los fragmentos recuperados.
