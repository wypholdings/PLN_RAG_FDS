# RAG FDS - Grupo I

Proyecto RAG para Fichas de Datos de Seguridad. El fabricante obligatorio del Grupo I es SIKA. Pintuco se usara como fabricante adicional para demostrar escalabilidad y generalizacion.

## Estado actual

- Fase 1 iniciada: diagnostico del corpus.
- Inventario generado para SIKA y Pintuco.
- Fase 2 avanzada: SIKA convertido completo a Markdown con deduplicacion.
- Fase 3 completada: chunks RAG de SIKA generados y validados.
- Fase 4 completada: indice vectorial local y retriever hibrido validados.
- Fase 5 completada: generacion con Ollama sobre chunks recuperados con fuentes obligatorias.
- Reportes disponibles en `data/reports`.
- Cumplimiento del documento guia documentado en `docs/CUMPLIMIENTO_GUIA.md`.

## Comandos

Usar el Python del entorno o un virtualenv propio.

```bash
python scripts/run_inventory.py --manufacturers SIKA Pintuco
```

```bash
python scripts/convert_pdfs.py --manufacturer SIKA --pilot
python scripts/convert_pdfs.py --manufacturer Pintuco --pilot
```

```bash
python scripts/convert_pdfs.py --manufacturer SIKA --all
```

```bash
python scripts/validate_conversion.py --manufacturer SIKA
```

```bash
python scripts/build_chunks.py --manufacturer SIKA
python scripts/validate_chunks.py --manufacturer SIKA
```

```bash
python scripts/build_vector_index.py --manufacturer SIKA
python scripts/retrieve.py --manufacturer SIKA --query "numero ONU transporte clase grupo de embalaje" --top-k 3
python scripts/test_retrieval.py --manufacturer SIKA
```

```bash
brew services start ollama
ollama pull qwen2.5:3b
source scripts/env_local.sh
.venv/bin/python scripts/ask.py --manufacturer SIKA --question "Cual es el telefono de emergencia?" --top-k 3
```

```bash
source scripts/env_local.sh
.venv/bin/streamlit run /Users/danielwilches/Downloads/PLN_ParcialFinalRAG_GrupoI/streamlit_app.py
```

## Estructura

```text
Documentos - Parcial final/   # PDFs fuente
data/reports/                 # reportes de diagnostico
data/processed/               # markdown, metadata, chunks e indices
docs/                         # documentacion tecnica
scripts/                      # comandos ejecutables
src/rag_fds/                  # codigo reutilizable del pipeline
```

## Objetivo de demo

La demo sera una app Streamlit con:

- consulta sobre SIKA preprocesado,
- Pintuco como extension,
- carga manual de PDFs desde navegador,
- respuestas con trazabilidad por documento, seccion, pagina y chunk,
- conexion a Ollama local como runtime principal.
