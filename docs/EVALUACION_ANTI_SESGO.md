# Evaluacion anti-sesgo del RAG_FDS

## Objetivo

Verificar que el sistema no esta ajustado unicamente a las preguntas de demo. La evaluacion usa preguntas nuevas, no usadas para construir el demo, distribuidas por secciones FDS y por fabricante.

El modelo generativo no fue fine-tuned ni entrenado con estas preguntas. La evaluacion mide si el recuperador trae evidencia correcta desde los documentos originales procesados.

## Sets evaluados

| Fabricante | Modo | Archivo ground truth | Preguntas | Observacion |
|---|---|---|---:|---|
| SIKA | Preprocesado | `data/ground_truth/sika_anti_bias_30.json` | 30 | Cubre secciones 1-16, CAS, EPP, transporte, telefonos y trazabilidad. |
| Pintuco | Preprocesado | `data/ground_truth/pintuco_anti_bias_30.json` | 30 | Cubre secciones 1-16, CAS, EPP, transporte, telefonos y trazabilidad. |
| CORONA | Subida manual simulada | `data/ground_truth/corona_manual_10.json` | 10 | Evalua PDFs cargables por la funcion manual. |
| Pintuland | Subida manual simulada | `data/ground_truth/pintuland_manual_10.json` | 10 | Evalua PDFs cargables por la funcion manual. |

## Resultados

| Fabricante | Preguntas | Top-1 seccion correcta | Top-K seccion correcta | Cobertura de terminos esperados |
|---|---:|---:|---:|---:|
| SIKA | 30 | 100.00% | 100.00% | 100.00% |
| Pintuco | 30 | 100.00% | 100.00% | 100.00% |
| CORONA manual | 10 | 90.00% | 100.00% | 100.00% |
| Pintuland manual | 10 | 100.00% | 100.00% | 100.00% |
| Total | 80 | 98.75% | 100.00% | 100.00% |

## Interpretacion

- El sistema no depende solo de las preguntas del demo: se evaluaron 80 preguntas nuevas sobre fabricantes, secciones y tipos de dato distintos.
- En todos los casos la seccion esperada aparece dentro del Top-K usado por el RAG.
- La unica falla Top-1 fue en CORONA para una pregunta de limites de exposicion de dioxido de titanio: el primer resultado fue composicion, pero la seccion 8 correcta aparecio en el Top-K y los terminos esperados estaban cubiertos.
- Esto respalda el uso de `Top-K = 3` a `5` en demo, porque la respuesta se genera con varias fuentes recuperadas y no con un unico fragmento.

## Reportes generados

| Reporte | Ruta |
|---|---|
| SIKA anti-sesgo | `data/reports/ground_truth_eval_sika_retrieval_only.json` |
| Pintuco anti-sesgo | `data/reports/ground_truth_eval_pintuco_retrieval_only.json` |
| CORONA manual | `data/reports/ground_truth_eval_corona_manual_retrieval_only.json` |
| Pintuland manual | `data/reports/ground_truth_eval_pintuland_manual_retrieval_only.json` |

## Comandos reproducibles

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
RAG_EMBEDDING_MODEL_PATH=/Users/danielwilches/.cache/huggingface/hub/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/snapshots/e8f8c211226b894fcb81acc59f3b34ba3efd5f42 \
.venv/bin/python scripts/evaluate_ground_truth.py \
  --manufacturer SIKA \
  --ground-truth data/ground_truth/sika_anti_bias_30.json \
  --top-k 5
```

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
RAG_EMBEDDING_MODEL_PATH=/Users/danielwilches/.cache/huggingface/hub/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/snapshots/e8f8c211226b894fcb81acc59f3b34ba3efd5f42 \
.venv/bin/python scripts/evaluate_ground_truth.py \
  --manufacturer Pintuco \
  --ground-truth data/ground_truth/pintuco_anti_bias_30.json \
  --top-k 5
```

Para CORONA y Pintuland se construyeron indices temporales en `data/runtime_uploads/eval_*`, simulando la funcionalidad de subida manual. Esa carpeta esta ignorada por Git para no mezclar datos temporales con el corpus preprocesado final.

