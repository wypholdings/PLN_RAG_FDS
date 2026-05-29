# Fase 3 - Chunking para RAG

## Objetivo

Construir fragmentos recuperables para RAG a partir de la metadata enriquecida de SIKA. Los chunks conservan texto, tablas, OCR de imagenes, referencias a assets y trazabilidad documental.

## Comandos

```bash
python scripts/build_chunks.py --manufacturer SIKA
python scripts/validate_chunks.py --manufacturer SIKA
```

## Salidas generadas

- `data/processed/chunks/sika_chunks.jsonl`
- `data/reports/chunk_report_sika.csv`
- `data/reports/chunk_summary_sika.json`
- `data/reports/chunk_validation_sika.json`

## Estrategia

- Unidad base: seccion normativa.
- Cada una de las 16 secciones de cada documento genera al menos un chunk.
- Las secciones se dividen si superan el tamano objetivo.
- Tamano objetivo: 850 tokens estimados.
- Solapamiento: 100 tokens estimados.
- Las tablas asociadas a una seccion se agregan al contenido recuperable del chunk.
- Las imagenes asociadas a una seccion se agregan como referencias de asset y texto OCR.

## Resultado SIKA

```json
{
  "manufacturer": "SIKA",
  "documents": 14,
  "chunks": 224,
  "sections_expected": 224,
  "sections_covered": 224,
  "content_type_counts": {
    "image": 107,
    "ocr": 107,
    "table": 32,
    "text": 224
  },
  "max_tokens": 850,
  "overlap_tokens": 100
}
```

Validacion:

```json
{
  "manufacturer": "SIKA",
  "chunks": 224,
  "expected_sections": 224,
  "covered_sections": 224,
  "missing_sections": [],
  "expected_tables": 39,
  "covered_tables": 39,
  "missing_tables": [],
  "expected_images": 174,
  "covered_images": 174,
  "missing_images": [],
  "empty_chunks": [],
  "missing_trace": [],
  "duplicate_chunk_ids": [],
  "status": "pass"
}
```

## Siguiente fase

Construir el indice vectorial local sobre `sika_chunks.jsonl`, implementar busqueda semantica y preparar el retriever que luego alimentara a Ollama.
