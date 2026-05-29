# Cumplimiento del documento guia

## Requerimientos aplicados

El documento guia exige:

- Convertir PDFs a Markdown.
- Preservar titulos, subtitulos, tablas, listas, notas y referencias cruzadas a imagenes o fuentes externas.
- Extraer e identificar las 16 secciones normativas.
- Tratar imagenes con OCR tradicional u otro parsing documental local.
- Asociar cada imagen a tabla, seccion o bloque tecnico mediante proximidad espacial, referencias textuales o metadatos estructurales.
- Incluir debajo de cada imagen una nota de trazabilidad.
- Evitar APIs pagas o servicios externos propietarios para la extraccion principal.

## Implementacion actual

| Exigencia | Implementacion |
|---|---|
| PDF a Markdown | `scripts/convert_pdfs.py` genera Markdown por documento |
| 16 secciones | `src/rag_fds/sections.py` detecta y valida secciones 1 a 16 |
| Tablas | PyMuPDF `find_tables()` extrae tablas y las inserta como Markdown |
| Imagenes/logos/pictogramas | PyMuPDF extrae imagenes embebidas como assets |
| OCR local | Tesseract local con idiomas `spa+eng` procesa las imagenes extraidas |
| Asociacion estructurada | Cada tabla/imagen se asocia a seccion por proximidad espacial y metadatos de pagina |
| Nota debajo de imagen | Cada imagen en Markdown tiene bloque `Nota de trazabilidad` inmediatamente debajo |
| Sin APIs pagas | Extraccion con herramientas locales open source |
| Duplicados | Hash de texto evita indexar dos veces el mismo documento |
| Trazabilidad RAG | Chunks JSONL conservan documento, seccion, paginas, tablas, imagenes y OCR |
| Recuperacion local | Indice local hibrido con embeddings multilingues y TF-IDF |
| Generacion local | Ollama local (`qwen2.5:3b`) como runtime principal |
| Evaluacion ground truth | 25 pares pregunta-respuesta con evaluacion retrieval y evaluacion con Ollama |

## Evidencia SIKA

Resultado de `python scripts/validate_conversion.py --manufacturer SIKA`:

```json
{
  "manufacturer": "SIKA",
  "documents_validated": 14,
  "documents_passed": 14,
  "documents_for_review": 0,
  "average_quality_score": 100.0,
  "duplicate_aliases": 1,
  "alias_errors": [],
  "asset_errors": []
}
```

Conteos del corpus SIKA convertido:

- 14 documentos canonicos.
- 1 duplicado registrado como alias.
- 224 secciones normativas validadas.
- 39 tablas extraidas como Markdown.
- 174 imagenes extraidas como assets con OCR y trazabilidad.
- 224 chunks RAG validados, cubriendo 224 secciones, 39 tablas y 174 imagenes.
- Indice local con 224 chunks y 384 dimensiones.
- Pruebas de recuperacion: 5/5 consultas con seccion correcta en top 1.
- Ground truth final: 25/25 top-1 correcto, 25/25 top-k correcto, 25/25 cobertura de contexto.
- Evaluacion con Ollama local: 25 respuestas evaluadas, `answer_term_pass_rate = 1.0`.

## Archivos de evidencia

- `data/reports/quality_report_sika.csv`
- `data/reports/quality_summary_sika.json`
- `data/reports/conversion_report_sika.csv`
- `data/processed/markdown/SIKA/`
- `data/processed/metadata/SIKA/`
- `data/processed/assets/SIKA/`
- `data/processed/chunks/sika_chunks.jsonl`
- `data/reports/chunk_validation_sika.json`
- `data/indexes/sika/`
- `data/reports/retrieval_test_report_sika.csv`
- `data/ground_truth/sika_ground_truth_25.json`
- `data/reports/ground_truth_eval_sika_retrieval_only.json`
- `data/reports/ground_truth_eval_sika_with_llm.json`
